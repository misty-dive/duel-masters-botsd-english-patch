from __future__ import annotations

from pathlib import Path

from .fontlink import ASCII_GLYPH_BYTES, decompress, page_geometry, parse_pac, unpack_4bpp


class GameFont:
    """Half-width ASCII renderer sourced directly from BOTSD FONTLINK.PAC."""

    def __init__(self, fontlink: str | Path | bytes):
        raw = fontlink if isinstance(fontlink, bytes) else Path(fontlink).read_bytes()
        entries = parse_pac(raw)
        self.pages: dict[str, bytes] = {}
        for entry in entries:
            if not (entry.name.startswith("half") and entry.name.endswith(".lz")):
                continue
            data = decompress(entry.blob)
            width, height, glyph_bytes, _ = page_geometry(data)
            if (width, height, glyph_bytes) == (12, 24, ASCII_GLYPH_BYTES):
                self.pages[entry.name] = data
        if not self.pages:
            raise ValueError("no half-width font pages found")

    def glyph(self, character: str):
        try:
            from PIL import Image
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Pillow is required for game-font rendering") from exc
        if len(character) != 1:
            raise ValueError("glyph expects one character")
        code = ord(character)
        if not 0x20 <= code <= 0x7F:
            raise ValueError(f"non-ASCII UI glyph {character!r}")
        number = code - 0x20
        page_number, index = divmod(number, 16)
        name = f"half{page_number:04d}.lz"
        if name not in self.pages:
            raise ValueError(f"FONTLINK page missing: {name}")
        data = self.pages[name]
        raw = data[8 + index * ASCII_GLYPH_BYTES : 8 + (index + 1) * ASCII_GLYPH_BYTES]
        pixels = unpack_4bpp(raw)
        image = Image.new("L", (12, 24))
        image.putdata([value * 17 for value in pixels])
        return image

    def text_mask(self, text: str, spacing: int = 1):
        try:
            from PIL import Image
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Pillow is required for game-font rendering") from exc
        glyphs = [self.glyph(character) for character in text]
        if not glyphs:
            return Image.new("L", (1, 1), 0)
        parts = []
        for glyph in glyphs:
            bbox = glyph.getbbox()
            parts.append(
                Image.new("L", (4, 24), 0)
                if bbox is None
                else glyph.crop((bbox[0], 0, bbox[2], 24))
            )
        width = sum(part.width for part in parts) + spacing * max(0, len(parts) - 1)
        output = Image.new("L", (max(1, width), 24), 0)
        x = 0
        for part in parts:
            output.paste(part, (x, 0))
            x += part.width + spacing
        bbox = output.getbbox()
        return output.crop(bbox) if bbox else Image.new("L", (1, 1), 0)
