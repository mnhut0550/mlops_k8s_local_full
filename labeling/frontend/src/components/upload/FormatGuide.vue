<template>
  <div class="card format-guide">
    <div class="guide-title">📋 Các format được hỗ trợ</div>
    <div class="guide-grid">

      <div class="guide-item">
        <div class="guide-badge badge-cls">Classification</div>
        <div class="guide-label">Folder có cấu trúc ImageFolder</div>
        <pre class="guide-tree">my_data/
  ├── cat/
  │   └── img1.jpg
  ├── dog/
  │   └── img2.jpg
  └── img_root.jpg  ← UNLABELED</pre>
        <div class="guide-note">→ Subfolder = class, auto gắn nhãn<br>→ Ảnh ở root → UNLABELED</div>
      </div>

      <div class="guide-item">
        <div class="guide-badge badge-dct">Detection (YOLO)</div>
        <div class="guide-label">Folder có đủ 3 thành phần</div>
        <pre class="guide-tree">my_data/
  ├── classes.txt   ← 1 class/dòng
  ├── images/
  │   └── img1.jpg
  └── labels/
      └── img1.txt  ← idx cx cy w h</pre>
        <div class="guide-note">→ Auto tạo class + import bbox<br>→ Không có .txt → UNLABELED</div>
      </div>

      <div class="guide-item">
        <div class="guide-badge badge-raw">Ảnh lẻ</div>
        <div class="guide-label">Chọn file thường</div>
        <pre class="guide-tree">img1.jpg
img2.png
img3.webp
...</pre>
        <div class="guide-note">→ Tất cả UNLABELED<br>→ Gắn nhãn thủ công trong tab Label</div>
      </div>

    </div>
  </div>
</template>

<style scoped>
.format-guide { padding: 16px 20px; }
.guide-title  { font-weight: 700; margin-bottom: 14px; font-size: 14px; }
.guide-grid   { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
@media (max-width: 900px) { .guide-grid { grid-template-columns: 1fr; } }
.guide-item   { background: #0f172a; border-radius: 8px; padding: 14px; }
.guide-badge  { display: inline-block; border-radius: 12px; padding: 2px 10px; font-size: 11px; font-weight: 700; margin-bottom: 8px; }
.badge-cls    { background: #1e3a5f; color: #93c5fd; border: 1px solid #3b82f6; }
.badge-dct    { background: #1e1040; color: #c4b5fd; border: 1px solid #7c3aed; }
.badge-raw    { background: #1c1c1c; color: #94a3b8; border: 1px solid #475569; }
.guide-label  { font-size: 12px; color: #94a3b8; margin-bottom: 8px; }
.guide-tree   {
  font-family: monospace; font-size: 11px; color: #cbd5e1;
  background: #1e293b; border-radius: 6px; padding: 8px 10px;
  margin: 0 0 8px; white-space: pre; overflow-x: auto; line-height: 1.6;
}
.guide-note   { font-size: 12px; color: #64748b; line-height: 1.6; }
</style>
