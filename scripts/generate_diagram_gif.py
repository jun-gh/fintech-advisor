"""Generate a clean, modern animated architecture diagram GIF for FintechDemo."""

import struct
from pathlib import Path

# --- 5x7 Pixel Font Bitmap Table (ASCII 32-126) ---
FONT = {
    ' ': [0, 0, 0, 0, 0, 0, 0],
    '!': [4, 4, 4, 4, 0, 0, 4],
    '"': [10, 10, 0, 0, 0, 0, 0],
    '#': [10, 31, 10, 10, 31, 10, 0],
    '$': [4, 15, 20, 14, 5, 30, 4],
    '%': [25, 26, 4, 8, 19, 19, 0],
    '&': [12, 18, 20, 9, 22, 17, 14],
    "'": [4, 4, 0, 0, 0, 0, 0],
    '(': [2, 4, 8, 8, 8, 4, 2],
    ')': [8, 4, 2, 2, 2, 4, 8],
    '*': [0, 10, 4, 31, 4, 10, 0],
    '+': [0, 4, 4, 31, 4, 4, 0],
    ',': [0, 0, 0, 0, 4, 4, 8],
    '-': [0, 0, 0, 31, 0, 0, 0],
    '.': [0, 0, 0, 0, 0, 12, 12],
    '/': [1, 2, 4, 8, 16, 0, 0],
    '0': [14, 17, 19, 21, 25, 17, 14],
    '1': [4, 12, 4, 4, 4, 4, 14],
    '2': [14, 17, 1, 2, 4, 8, 31],
    '3': [31, 2, 4, 2, 1, 17, 14],
    '4': [2, 6, 10, 18, 31, 2, 2],
    '5': [31, 16, 30, 1, 1, 17, 14],
    '6': [6, 8, 16, 30, 17, 17, 14],
    '7': [31, 1, 2, 4, 8, 8, 8],
    '8': [14, 17, 17, 14, 17, 17, 14],
    '9': [14, 17, 17, 15, 1, 2, 12],
    ':': [0, 12, 12, 0, 12, 12, 0],
    ';': [0, 12, 12, 0, 12, 4, 8],
    '<': [2, 4, 8, 16, 8, 4, 2],
    '=': [0, 31, 0, 31, 0, 0, 0],
    '>': [8, 4, 2, 1, 2, 4, 8],
    '?': [14, 17, 1, 2, 4, 0, 4],
    '@': [14, 17, 21, 21, 17, 16, 14],
    'A': [14, 17, 17, 31, 17, 17, 17],
    'B': [30, 17, 17, 30, 17, 17, 30],
    'C': [14, 17, 16, 16, 16, 17, 14],
    'D': [28, 18, 17, 17, 17, 18, 28],
    'E': [31, 16, 16, 30, 16, 16, 31],
    'F': [31, 16, 16, 30, 16, 16, 16],
    'G': [14, 17, 16, 23, 17, 17, 14],
    'H': [17, 17, 17, 31, 17, 17, 17],
    'I': [14, 4, 4, 4, 4, 4, 14],
    'J': [7, 2, 2, 2, 2, 18, 12],
    'K': [17, 18, 20, 24, 20, 18, 17],
    'L': [16, 16, 16, 16, 16, 16, 31],
    'M': [17, 27, 21, 21, 17, 17, 17],
    'N': [17, 25, 21, 19, 17, 17, 17],
    'O': [14, 17, 17, 17, 17, 17, 14],
    'P': [30, 17, 17, 30, 16, 16, 16],
    'Q': [14, 17, 17, 17, 21, 18, 13],
    'R': [30, 17, 17, 30, 20, 18, 17],
    'S': [14, 17, 16, 14, 1, 17, 14],
    'T': [31, 4, 4, 4, 4, 4, 4],
    'U': [17, 17, 17, 17, 17, 17, 14],
    'V': [17, 17, 17, 17, 17, 10, 4],
    'W': [17, 17, 17, 21, 21, 27, 17],
    'X': [17, 17, 10, 4, 10, 17, 17],
    'Y': [17, 17, 17, 10, 4, 4, 4],
    'Z': [31, 1, 2, 4, 8, 16, 31],
    '[': [14, 8, 8, 8, 8, 8, 14],
    '\\': [16, 8, 4, 2, 1, 0, 0],
    ']': [14, 2, 2, 2, 2, 2, 14],
    '^': [4, 10, 17, 0, 0, 0, 0],
    '_': [0, 0, 0, 0, 0, 0, 31],
    '`': [8, 4, 2, 0, 0, 0, 0],
    'a': [0, 0, 14, 1, 15, 17, 15],
    'b': [16, 16, 22, 25, 17, 17, 30],
    'c': [0, 0, 14, 16, 16, 17, 14],
    'd': [1, 1, 13, 19, 17, 17, 15],
    'e': [0, 0, 14, 17, 31, 16, 14],
    'f': [6, 9, 8, 28, 8, 8, 8],
    'g': [0, 0, 15, 17, 17, 15, 1],
    'h': [16, 16, 22, 25, 17, 17, 17],
    'i': [4, 0, 12, 4, 4, 4, 14],
    'j': [2, 0, 6, 2, 2, 18, 12],
    'k': [16, 16, 18, 20, 24, 20, 18],
    'l': [12, 4, 4, 4, 4, 4, 14],
    'm': [0, 0, 26, 21, 21, 17, 17],
    'n': [0, 0, 22, 25, 17, 17, 17],
    'o': [0, 0, 14, 17, 17, 17, 14],
    'p': [0, 0, 30, 17, 30, 16, 16],
    'q': [0, 0, 15, 17, 15, 1, 1],
    'r': [0, 0, 22, 25, 16, 16, 16],
    's': [0, 0, 15, 16, 14, 1, 30],
    't': [8, 8, 28, 8, 8, 9, 6],
    'u': [0, 0, 17, 17, 17, 19, 13],
    'v': [0, 0, 17, 17, 17, 10, 4],
    'w': [0, 0, 17, 17, 21, 21, 10],
    'x': [0, 0, 17, 10, 4, 10, 17],
    'y': [0, 0, 17, 17, 15, 1, 14],
    'z': [0, 0, 31, 2, 4, 8, 31],
    '{': [2, 4, 4, 8, 4, 4, 2],
    '|': [4, 4, 4, 4, 4, 4, 4],
    '}': [8, 4, 4, 2, 4, 4, 8],
    '~': [0, 0, 8, 21, 2, 0, 0],
    '•': [0, 0, 14, 14, 14, 0, 0],
}


# --- Color Palette (Light Mode Design System) ---
PALETTE = [
    (248, 250, 252),  # 0: Background Canvas (#F8FAFC)
    (255, 255, 255),  # 1: Pure White (#FFFFFF)
    (226, 232, 240),  # 2: Border Light (#E2E8F0)
    (203, 213, 225),  # 3: Border Medium (#CBD5E1)
    (148, 163, 184),  # 4: Arrow Muted (#94A3B8)
    (15, 23, 42),     # 5: Text Dark (#0F172A)
    (71, 85, 105),    # 6: Text Muted (#475569)
    (100, 116, 139),  # 7: Text Subtle (#64748B)

    # Vercel / Client Tier (Indigo/Violet)
    (245, 243, 255),  # 8: Card Fill (#F5F3FF)
    (199, 210, 254),  # 9: Card Border (#C7D2FE)
    (79, 70, 229),    # 10: Accent / Badge (#4F46E5)

    # AWS Lambda (Amber/Orange)
    (255, 251, 235),  # 11: Card Fill (#FFFBEB)
    (253, 230, 138),  # 12: Card Border (#FDE68A)
    (217, 119, 6),    # 13: Accent / Badge (#D97706)

    # LangGraph (Emerald/Teal)
    (236, 253, 245),  # 14: Card Fill (#ECFDF5)
    (167, 243, 208),  # 15: Card Border (#A7F3D0)
    (5, 150, 105),    # 16: Accent / Badge (#059669)

    # Neon PostgreSQL (Cyan/Sky)
    (240, 249, 255),  # 17: Card Fill (#F0F9FF)
    (186, 230, 253),  # 18: Card Border (#BAE6FD)
    (2, 132, 199),    # 19: Accent / Badge (#0284C7)

    # Google Gemini (Blue)
    (239, 246, 255),  # 20: Card Fill (#EFF6FF)
    (191, 219, 254),  # 21: Card Border (#BFDBFE)
    (37, 99, 235),    # 22: Accent / Badge (#2563EB)

    # Animated Pulse Highlights
    (59, 130, 246),   # 23: Bright Blue Pulse (#3B82F6)
    (16, 185, 129),   # 24: Bright Green Pulse (#10B981)
    (244, 63, 94),    # 25: Rose Pulse (#F43F5E)
]


class Canvas:
    def __init__(self, width: int = 1000, height: int = 500, bg_idx: int = 0):
        self.width = width
        self.height = height
        self.bg_idx = bg_idx
        self.pixels = [bg_idx] * (width * height)

    def set_pixel(self, x: int, y: int, color_idx: int):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.pixels[y * self.width + x] = color_idx

    def draw_rect(self, x: int, y: int, w: int, h: int, color_idx: int):
        x_end = min(self.width, x + w)
        y_end = min(self.height, y + h)
        x_start = max(0, x)
        y_start = max(0, y)
        for cy in range(y_start, y_end):
            offset = cy * self.width
            for cx in range(x_start, x_end):
                self.pixels[offset + cx] = color_idx

    def draw_rounded_rect(self, x: int, y: int, w: int, h: int, r: int, fill_idx: int, border_idx: int | None = None):
        self.draw_rect(x + r, y, w - 2 * r, h, fill_idx)
        self.draw_rect(x, y + r, r, h - 2 * r, fill_idx)
        self.draw_rect(x + w - r, y + r, r, h - 2 * r, fill_idx)

        # corners
        for dy in range(r):
            for dx in range(r):
                if (r - 1 - dx) ** 2 + (r - 1 - dy) ** 2 <= r ** 2:
                    self.set_pixel(x + dx, y + dy, fill_idx)
                    self.set_pixel(x + w - 1 - dx, y + dy, fill_idx)
                    self.set_pixel(x + dx, y + h - 1 - dy, fill_idx)
                    self.set_pixel(x + w - 1 - dx, y + h - 1 - dy, fill_idx)

        if border_idx is not None:
            # horizontal borders
            for cx in range(x + r, x + w - r):
                self.set_pixel(cx, y, border_idx)
                self.set_pixel(cx, y + h - 1, border_idx)
            # vertical borders
            for cy in range(y + r, y + h - r):
                self.set_pixel(x, cy, border_idx)
                self.set_pixel(x + w - 1, cy, border_idx)

    def draw_text(self, x: int, y: int, text: str, color_idx: int, scale: int = 1):
        cur_x = x
        for ch in text:
            bitmap = FONT.get(ch, FONT[' '])
            for row_idx, row in enumerate(bitmap):
                for col_idx in range(5):
                    if (row >> (4 - col_idx)) & 1:
                        if scale == 1:
                            self.set_pixel(cur_x + col_idx, y + row_idx, color_idx)
                        else:
                            for sy in range(scale):
                                for sx in range(scale):
                                    self.set_pixel(cur_x + col_idx * scale + sx, y + row_idx * scale + sy, color_idx)
            cur_x += (6 * scale)

    def draw_badge(self, x: int, y: int, text: str, bg_idx: int, text_idx: int = 1):
        text_w = len(text) * 6
        pad_x = 6
        pad_y = 3
        badge_w = text_w + pad_x * 2
        badge_h = 7 + pad_y * 2
        self.draw_rounded_rect(x, y, badge_w, badge_h, 3, bg_idx)
        self.draw_text(x + pad_x, y + pad_y, text, text_idx, scale=1)

    def draw_h_arrow(self, x1: int, x2: int, y: int, color_idx: int, label: str = "", label_y_offset: int = -12):
        step = 1 if x2 >= x1 else -1
        for cx in range(x1, x2, step):
            self.set_pixel(cx, y, color_idx)
            self.set_pixel(cx, y + 1, color_idx)

        # arrow head
        if x2 > x1:
            for d in range(6):
                self.set_pixel(x2 - d, y - d, color_idx)
                self.set_pixel(x2 - d, y + 1 + d, color_idx)
        else:
            for d in range(6):
                self.set_pixel(x2 + d, y - d, color_idx)
                self.set_pixel(x2 + d, y + 1 + d, color_idx)

        if label:
            label_w = len(label) * 6
            mid_x = (x1 + x2) // 2 - label_w // 2
            self.draw_text(mid_x, y + label_y_offset, label, color_idx, scale=1)

    def draw_glow_circle(self, cx: int, cy: int, r: int, color_idx: int):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy <= r * r:
                    self.set_pixel(cx + dx, cy + dy, color_idx)


# --- GIF LZW Compressor ---
def lzw_compress(indices: list[int], min_code_size: int) -> bytes:
    clear_code = 1 << min_code_size
    eoi_code = clear_code + 1
    code_size = min_code_size + 1
    max_code = 1 << code_size
    next_code = eoi_code + 1
    dictionary = {bytes([i]): i for i in range(clear_code)}

    bits = 0
    bit_count = 0
    output_bytes = bytearray()

    def emit(code: int):
        nonlocal bits, bit_count, output_bytes
        bits |= (code << bit_count)
        bit_count += code_size
        while bit_count >= 8:
            output_bytes.append(bits & 0xFF)
            bits >>= 8
            bit_count -= 8

    emit(clear_code)
    pattern = bytearray()
    for idx in indices:
        new_pattern = pattern + bytes([idx])
        if bytes(new_pattern) in dictionary:
            pattern = new_pattern
        else:
            emit(dictionary[bytes(pattern)])
            if next_code < 4096:
                dictionary[bytes(new_pattern)] = next_code
                next_code += 1
                if next_code > max_code and code_size < 12:
                    code_size += 1
                    max_code = 1 << code_size
            else:
                emit(clear_code)
                code_size = min_code_size + 1
                max_code = 1 << code_size
                dictionary = {bytes([i]): i for i in range(clear_code)}
                next_code = eoi_code + 1
            pattern = bytearray([idx])

    if pattern:
        emit(dictionary[bytes(pattern)])
    emit(eoi_code)

    if bit_count > 0:
        output_bytes.append(bits & 0xFF)

    blocks = bytearray([min_code_size])
    for i in range(0, len(output_bytes), 255):
        chunk = output_bytes[i:i + 255]
        blocks.append(len(chunk))
        blocks.extend(chunk)
    blocks.append(0)
    return bytes(blocks)


def write_gif(filename: str, width: int, height: int, palette: list[tuple[int, int, int]], frames: list[list[int]], delay_cs: int = 15):
    color_count = len(palette)
    bpp = 1
    while (1 << bpp) < color_count:
        bpp += 1
    bpp = max(2, bpp)
    padded_palette = list(palette) + [(0, 0, 0)] * ((1 << bpp) - color_count)
    palette_bytes = bytearray()
    for r, g, b in padded_palette:
        palette_bytes.extend([r, g, b])

    out = bytearray(b'GIF89a')
    out.extend(struct.pack('<HHBBB', width, height, 0x80 | ((bpp - 1) << 4) | (bpp - 1), 0, 0))
    out.extend(palette_bytes)
    # Netscape 2.0 loop block
    out.extend(b'\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00')

    for frame in frames:
        out.extend(struct.pack('<BBBBHBB', 0x21, 0xF9, 4, 0x04, delay_cs, 0, 0))
        out.extend(struct.pack('<BHHHHB', 0x2C, 0, 0, width, height, 0))
        out.extend(lzw_compress(frame, max(2, bpp)))

    out.append(0x3B)
    Path(filename).parent.mkdir(parents=True, exist_ok=True)
    with open(filename, 'wb') as f:
        f.write(out)
    print(f"Generated GIF: {filename} ({len(out)} bytes, {len(frames)} frames)")


def render_base_scene() -> Canvas:
    c = Canvas(1000, 500, bg_idx=0)

    # Subtle Header Section
    c.draw_rect(0, 0, 1000, 56, 1)
    c.draw_rect(0, 56, 1000, 1, 2)
    c.draw_text(30, 16, "FintechDemo — Serverless RAG & Compliance Architecture", 5, scale=2)
    c.draw_text(30, 38, "Event-Driven Reactive Streaming & Fail-Closed Hybrid Grounding", 7, scale=1)
    c.draw_badge(850, 20, "LIVE DEMO", 10, 1)

    # --- Card 1: Vercel React SPA (Client) ---
    c.draw_rounded_rect(30, 80, 200, 370, 6, 8, 9)
    c.draw_badge(45, 96, "CLIENT TIER", 10, 1)
    c.draw_text(45, 126, "Vercel React SPA", 5, scale=2)
    c.draw_text(45, 150, "Vite 6 + React 19", 6, scale=1)

    c.draw_rect(45, 175, 170, 1, 9)
    c.draw_text(45, 190, "• Copilot Q&A UI", 6, scale=1)
    c.draw_text(45, 215, "• SSE Stage Bars", 6, scale=1)
    c.draw_text(45, 240, "• PII Masking View", 6, scale=1)
    c.draw_text(45, 265, "• Native <dialog>", 6, scale=1)
    c.draw_text(45, 290, "• Audit Trail Log", 6, scale=1)
    c.draw_text(45, 315, "• Light/Dark Theme", 6, scale=1)

    c.draw_rounded_rect(45, 385, 170, 45, 4, 1, 9)
    c.draw_text(55, 395, "Endpoint:", 7, scale=1)
    c.draw_text(55, 412, "/api/v1/copilot/query", 10, scale=1)

    # --- Card 2: AWS Lambda (Compute) ---
    c.draw_rounded_rect(270, 80, 200, 370, 6, 11, 12)
    c.draw_badge(285, 96, "SERVERLESS COMPUTE", 13, 1)
    c.draw_text(285, 126, "AWS Lambda", 5, scale=2)
    c.draw_text(285, 150, "ap-southeast-2 (Sydney)", 6, scale=1)

    c.draw_rect(285, 175, 170, 1, 12)
    c.draw_text(285, 190, "• Lambda Web Adapter", 6, scale=1)
    c.draw_text(285, 208, "  (LWA 1.1.0)", 7, scale=1)
    c.draw_text(285, 230, "• InvokeMode:", 6, scale=1)
    c.draw_text(285, 248, "  RESPONSE_STREAM", 13, scale=1)
    c.draw_text(285, 270, "• Python 3.13 FastAPI", 6, scale=1)
    c.draw_text(285, 295, "• Uniform ErrorEnvelope", 6, scale=1)
    c.draw_text(285, 320, "• CORS & X-Request-ID", 6, scale=1)

    c.draw_rounded_rect(285, 385, 170, 45, 4, 1, 12)
    c.draw_text(295, 395, "Container Image:", 7, scale=1)
    c.draw_text(295, 412, "ECR (linux/amd64)", 13, scale=1)

    # --- Card 3: LangGraph (Orchestration) ---
    c.draw_rounded_rect(510, 80, 210, 370, 6, 14, 15)
    c.draw_badge(525, 96, "ORCHESTRATION", 16, 1)
    c.draw_text(525, 126, "LangGraph Copilot", 5, scale=2)
    c.draw_text(525, 150, "StateGraph (TypedDict)", 6, scale=1)

    c.draw_rect(525, 175, 180, 1, 15)
    c.draw_text(525, 190, "1. guardrail_node", 16, scale=1)
    c.draw_text(540, 208, "• Luhn PAN Masking", 7, scale=1)
    c.draw_text(540, 224, "• Delimiter Wrapping", 7, scale=1)

    c.draw_text(525, 246, "2. retrieve_node", 16, scale=1)
    c.draw_text(540, 264, "• Hybrid Dense + FTS", 7, scale=1)
    c.draw_text(540, 280, "• RRF Fusion (k=60)", 7, scale=1)

    c.draw_text(525, 302, "3. generate_node", 16, scale=1)
    c.draw_text(540, 320, "• Strict Chunk Gate", 7, scale=1)
    c.draw_text(540, 336, "• Fail-Closed Refusal", 7, scale=1)

    c.draw_text(525, 358, "4. audit_node", 16, scale=1)
    c.draw_text(540, 376, "• Immutable SQL Log", 7, scale=1)

    # --- Card 4A: Neon PostgreSQL (Data Tier) ---
    c.draw_rounded_rect(760, 80, 210, 170, 6, 17, 18)
    c.draw_badge(775, 96, "VECTOR + FTS", 19, 1)
    c.draw_text(775, 126, "Neon PostgreSQL", 5, scale=2)
    c.draw_text(775, 150, "Serverless Postgres 16", 6, scale=1)
    c.draw_rect(775, 168, 180, 1, 18)
    c.draw_text(775, 180, "• pgvector 0.8.0 (HNSW)", 6, scale=1)
    c.draw_text(775, 202, "• TSVECTOR GIN index", 6, scale=1)
    c.draw_text(775, 224, "• Transaction Pooler (-pooler)", 7, scale=1)

    # --- Card 4B: Google Gemini (AI Tier) ---
    c.draw_rounded_rect(760, 280, 210, 170, 6, 20, 21)
    c.draw_badge(775, 296, "LLM INFERENCE", 22, 1)
    c.draw_text(775, 326, "Google Gemini", 5, scale=2)
    c.draw_text(775, 350, "Structured Output SDK", 6, scale=1)
    c.draw_rect(775, 368, 180, 1, 21)
    c.draw_text(775, 380, "• Primary: 3.6 Flash", 22, scale=1)
    c.draw_text(775, 402, "• Fallback: 3.5 Flash", 6, scale=1)
    c.draw_text(775, 424, "• 768-dim Embeddings", 7, scale=1)

    # --- Connecting Arrows ---
    # 1. Vercel <-> Lambda (Request top, Stream bottom)
    c.draw_h_arrow(230, 270, 220, 4, label="HTTPS Req", label_y_offset=-14)
    c.draw_h_arrow(270, 230, 310, 10, label="SSE Stream", label_y_offset=6)

    # 2. Lambda -> LangGraph
    c.draw_h_arrow(470, 510, 260, 4, label="FastAPI", label_y_offset=-14)

    # 3. LangGraph <-> Neon
    c.draw_h_arrow(720, 760, 160, 19, label="RRF Search", label_y_offset=-14)

    # 4. LangGraph <-> Gemini
    c.draw_h_arrow(720, 760, 360, 22, label="JSON Schema", label_y_offset=-14)

    return c


def generate_animated_diagram():
    frames = []
    total_frames = 24
    base = render_base_scene()

    for f_idx in range(total_frames):
        # copy pixels
        frame_pixels = list(base.pixels)
        frame_canvas = Canvas(base.width, base.height, bg_idx=0)
        frame_canvas.pixels = frame_pixels

        # --- Animated Pulse Path ---
        # Stage 1: Vercel to Lambda (f: 0..5)
        if 0 <= f_idx < 6:
            progress = f_idx / 5.0
            px = int(230 + progress * 40)
            py = 220
            frame_canvas.draw_glow_circle(px, py, 4, 23)
            frame_canvas.draw_text(230, 185, "Sanitizing...", 10, scale=1)

        # Stage 2: Lambda into LangGraph (f: 6..11)
        elif 6 <= f_idx < 12:
            progress = (f_idx - 6) / 5.0
            px = int(470 + progress * 40)
            py = 260
            frame_canvas.draw_glow_circle(px, py, 4, 24)
            # highlight LangGraph box
            frame_canvas.draw_badge(525, 96, "ORCHESTRATING", 24, 1)

        # Stage 3: LangGraph to Neon & Gemini (f: 12..17)
        elif 12 <= f_idx < 18:
            progress = (f_idx - 12) / 5.0
            px = int(720 + progress * 40)
            frame_canvas.draw_glow_circle(px, 160, 4, 19)
            frame_canvas.draw_glow_circle(px, 360, 4, 22)
            frame_canvas.draw_badge(775, 96, "RETRIEVING...", 19, 1)
            frame_canvas.draw_badge(775, 296, "GENERATING...", 22, 1)

        # Stage 4: SSE streaming back to Vercel (f: 18..23)
        else:
            progress = (f_idx - 18) / 5.0
            px = int(270 - progress * 40)
            py = 310
            frame_canvas.draw_glow_circle(px, py, 5, 24)
            frame_canvas.draw_text(220, 330, "event: result", 16, scale=1)

        frames.append(frame_canvas.pixels)

    # Save to documentation and frontend public directories
    write_gif("docs/architecture.gif", 1000, 500, PALETTE, frames, delay_cs=12)
    write_gif("frontend/public/architecture.gif", 1000, 500, PALETTE, frames, delay_cs=12)
    print("Done generating architecture GIFs!")


if __name__ == "__main__":
    generate_animated_diagram()
