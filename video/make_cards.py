"""Title cards for the demo video (a3): S1, S2, S7 as 1920x1080 PNGs in video/cards/."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
BG, INK, MUTED, ACCENT = "#ffffff", "#1f2933", "#52606d", "#5b3cc4"  # accent: Crustdata violet
OUT = Path(__file__).parent / "cards"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    names = ["segoeuib.ttf", "arialbd.ttf"] if bold else ["segoeui.ttf", "arial.ttf"]
    names += ["DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def wrap(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=f) <= width:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    return [*lines, cur] if cur else lines


def card(name: str, blocks: list[tuple[str, int, bool, str]], gap: int = 36) -> Path:
    """blocks: (text, size, bold, colour), stacked and centred vertically and horizontally."""
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    laid = []
    for text, size, bold, colour in blocks:
        f = font(size, bold)
        rows = wrap(d, text, f, W - 320)
        laid.append((rows, f, colour, int(size * 1.25)))
    total = sum(len(rows) * lh for rows, _, _, lh in laid) + gap * (len(laid) - 1)
    y = (H - total) // 2
    for rows, f, colour, lh in laid:
        for row in rows:
            d.text(((W - d.textlength(row, font=f)) // 2, y), row, font=f, fill=colour)
            y += lh
        y += gap
    d.rectangle([0, H - 18, W, H], fill=ACCENT)  # accent band
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.png"
    img.save(path)
    return path


if __name__ == "__main__":
    card(
        "S1",
        [
            ("An anonymous tip:", 56, False, MUTED),
            ("“A manager keeps pushing payments to one supplier.”", 84, True, INK),
            (
                "Proving it today: weeks of manual audit work. Risk: accusing the innocent.",
                46,
                False,
                ACCENT,
            ),
        ],
        gap=56,
    )
    card("S2", [("Built for internal auditors & audit committees", 92, True, INK)])
    card(
        "S7",
        [
            ("Casefile", 150, True, INK),
            (
                "Every fake caught · No honest business turned away · Every fact traceable",
                44,
                False,
                MUTED,
            ),
            ("Built on Crustdata’s identity graph", 52, True, ACCENT),
        ],
        gap=48,
    )
    print("cards written to", OUT)
