import sqlite3
from dataclasses import dataclass

from pokebot.db import now
from pokebot.matching import match_card

CONDITIONS = ("NM", "LP", "MP", "HP", "DMG", "unknown")
MAX_IMAGES = 3

TOOL = {
    "name": "report_card",
    "description": "Registra a carta Pokémon vista nas fotos do anúncio e o estado estimado dela.",
    "input_schema": {
        "type": "object",
        "properties": {
            "card_name": {"type": ["string", "null"], "description": "Nome da carta como impresso, ou null se não der para ler"},
            "card_number": {"type": ["string", "null"], "description": "Número impresso, ex.: 194/203, ou null"},
            "set_name": {"type": ["string", "null"]},
            "card_confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "condition": {
                "type": "string",
                "enum": list(CONDITIONS),
                "description": "NM quase nova, LP leve desgaste, MP desgaste moderado, HP muito desgastada, DMG danificada, unknown se as fotos não permitem avaliar",
            },
            "condition_confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "in_protective_case": {"type": "boolean", "description": "Carta dentro de sleeve, pasta, top loader ou case"},
            "notes": {"type": "string", "description": "Defeitos visíveis, reflexo, foto borrada etc., em uma ou duas frases"},
        },
        "required": ["card_confidence", "condition", "condition_confidence", "in_protective_case", "notes"],
    },
}

PROMPT = (
    "Você avalia anúncios de cartas Pokémon para um revendedor. Título do anúncio: {title!r}.\n"
    "Identifique a carta nas fotos (nome e número impresso) e estime o estado pela centralização, cantos, bordas e superfície. "
    "Seja conservador: se a carta está em sleeve/pasta, há reflexo, a foto é pequena ou só mostra a frente, "
    "baixe a confiança da condição e diga isso nas notas; use 'unknown' quando não der para avaliar. "
    "Não invente: se não conseguir ler o número, devolva null. Chame report_card."
)


@dataclass
class VisionResult:
    card_name: str | None
    card_number: str | None
    set_name: str | None
    card_confidence: float
    condition: str
    condition_confidence: float
    in_protective_case: bool
    notes: str


def analyze_images(client, model: str, title: str, image_urls: list[str]) -> VisionResult:
    """Pede ao modelo de visão a carta e o estado. `client` é um anthropic.Anthropic."""
    content = [{"type": "image", "source": {"type": "url", "url": u}} for u in image_urls[:MAX_IMAGES]]
    content.append({"type": "text", "text": PROMPT.format(title=title)})
    resp = client.messages.create(
        model=model,
        max_tokens=1024,
        tools=[TOOL],
        tool_choice={"type": "tool", "name": TOOL["name"]},
        messages=[{"role": "user", "content": content}],
    )
    block = next((b for b in resp.content if getattr(b, "type", None) == "tool_use"), None)
    if block is None:
        raise ValueError("o modelo não devolveu report_card")
    d = block.input
    condition = d.get("condition") if d.get("condition") in CONDITIONS else "unknown"
    return VisionResult(
        card_name=d.get("card_name"),
        card_number=d.get("card_number"),
        set_name=d.get("set_name"),
        card_confidence=float(d.get("card_confidence", 0)),
        condition=condition,
        condition_confidence=float(d.get("condition_confidence", 0)),
        in_protective_case=bool(d.get("in_protective_case", False)),
        notes=d.get("notes", ""),
    )


def analyze_pending(conn: sqlite3.Connection, client, model: str, limit: int) -> tuple[int, int]:
    """Analisa anúncios com foto e ainda sem análise (os mais novos primeiro).

    Devolve (analisados, falhas). Se o título não bastou para achar a carta, tenta de novo com o número lido na foto.
    """
    rows = conn.execute(
        "SELECT l.id, l.title, l.card_id FROM listings l"
        " WHERE NOT EXISTS (SELECT 1 FROM listing_analysis a WHERE a.listing_id = l.id)"
        " AND EXISTS (SELECT 1 FROM listing_images i WHERE i.listing_id = l.id)"
        " ORDER BY l.first_seen_at DESC, l.id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    done = failed = 0
    for row in rows:
        urls = [r["url"] for r in conn.execute("SELECT url FROM listing_images WHERE listing_id = ?", (row["id"],))]
        try:
            res = analyze_images(client, model, row["title"], urls)
        except Exception:
            failed += 1
            continue
        conn.execute(
            "INSERT INTO listing_analysis (listing_id, card_name, card_number, set_name, card_confidence, condition,"
            " condition_confidence, in_protective_case, notes, model, analyzed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                row["id"], res.card_name, res.card_number, res.set_name, res.card_confidence, res.condition,
                res.condition_confidence, int(res.in_protective_case), res.notes, model, now(),
            ),
        )
        if not row["card_id"] and res.card_name and res.card_number:
            card_id = match_card(conn, f"{res.card_name} {res.card_number}")
            if card_id:
                conn.execute("UPDATE listings SET card_id = ? WHERE id = ?", (card_id, row["id"]))
        conn.commit()
        done += 1
    return done, failed
