# -*- coding: utf-8 -*-
import csv
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import traceback
from datetime import date, datetime, timedelta

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QDateEdit, QDialog,
    QDialogButtonBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QProgressDialog, QPushButton, QStyledItemDelegate, QTabWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))


def _pick_data_dir():
    """数据默认放在程序旁边；若程序所在目录没有写权限（例如装在 C:\\Program Files、
    或者整个文件夹被设成只读），自动退回 %LOCALAPPDATA%\车辆管理系统\数据，
    保证换台电脑、换个目录也能正常保存，不会一点保存就报错。"""
    beside = os.path.join(APP_DIR, "数据")
    try:
        os.makedirs(os.path.join(beside, "每日信息"), exist_ok=True)
        probe = os.path.join(beside, ".write_test")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(probe)
        return beside
    except Exception:
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        fallback = os.path.join(base, "车辆管理系统", "数据")
        os.makedirs(os.path.join(fallback, "每日信息"), exist_ok=True)
        return fallback


DATA_DIR = _pick_data_dir()
DATA_IS_FALLBACK = os.path.abspath(DATA_DIR) != os.path.abspath(os.path.join(APP_DIR, "数据"))
DAILY_DIR = os.path.join(DATA_DIR, "每日信息")
DRIVER_FILE = os.path.join(DATA_DIR, "司机身份登记表.csv")
STATS_APP = os.path.join(APP_DIR, "车辆运货统计表.py")

DAILY_HEADER = ["车牌号", "装车时间", "卸货时间", "装车净重", "卸货净重", "身份证号", "司机姓名", "司机电话", "目前状态", "电车or油车", "抬头"]
DRIVER_HEADER = ["身份证号", "司机姓名", "司机电话", "车牌号"]
COL_W = [110, 165, 165, 85, 85, 185, 95, 125, 80, 95, 230]

PLATE_PROV = "京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼"
PLATE_RE = re.compile(rf"[{PLATE_PROV}][A-Za-z][A-Za-z0-9]{{4,5}}[A-Za-z0-9挂学警]")
TIME_RE = re.compile(r"(\d{4}[-/年.]\d{1,2}[-/月.]\d{1,2}日?\s+\d{1,2}:\d{2}(?::\d{2})?)")
TIME_SHORT_RE = re.compile(r"(?<![\d:])(\d{1,2}:\d{2}(?::\d{2})?)(?![\d:])")
NUM_RE = re.compile(r"(\d+(?:\.\d+)?)")
PHONE_RE = re.compile(r"1\d{10}")
ID_RE = re.compile(r"\d{17}[\dXx]")
COMPANY_KEYS = ("公司", "集团", "物流", "煤业", "矿业", "建材", "贸易", "运输", "供应链", "科技", "实业", "工贸", "汽贸", "洗煤", "石料", "砂石", "钢铁", "焦化", "化工", "能源", "冶金", "物产")
WATERMARK_KEYS = ("磅单", "有限公", "钢铁", "计量", "物资", "公司")

# ---------------------------------------------------------------- 界面主题
# 只做视觉：统一的浅色工作台风格，不改变任何交互逻辑。
THEME_QSS = """
* {
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 10pt;
    color: #1f2937;
}
QMainWindow, QDialog { background: #f3f5f9; }
QWidget#tabPage { background: #f3f5f9; }
QTabWidget::pane { border: none; background: #f3f5f9; }
QTabBar::tab {
    background: transparent; color: #5b6472;
    padding: 8px 22px; margin: 7px 4px 0 0;
    border-radius: 8px 8px 0 0; font-weight: 600;
}
QTabBar::tab:hover { color: #2563eb; }
QTabBar::tab:selected { background: #ffffff; color: #2563eb; }
QPushButton {
    background: #ffffff; border: 1px solid #d7deea; border-radius: 7px;
    padding: 7px 16px; color: #374151;
}
QPushButton:hover { border-color: #2563eb; color: #2563eb; background: #f8fbff; }
QPushButton:pressed { background: #eef3fd; }
QPushButton:disabled { color: #b3bac6; border-color: #e5e9f0; background: #f7f8fa; }
QPushButton#primary {
    background: #2563eb; border: 1px solid #2563eb; color: #ffffff; font-weight: 600;
}
QPushButton#primary:hover { background: #1d4ed8; border-color: #1d4ed8; color: #ffffff; }
QPushButton#primary:pressed { background: #1e40af; }
QPushButton#accent {
    background: #eff5ff; border: 1px solid #bcd2fb; color: #1d4ed8; font-weight: 600;
}
QPushButton#accent:hover { background: #e2edff; border-color: #2563eb; color: #1d4ed8; }
QPushButton#danger { background: #ffffff; border: 1px solid #f0c7c7; color: #d23c3c; }
QPushButton#danger:hover { background: #fdf3f3; border-color: #dc2626; color: #b91c1c; }
QPushButton#ghost { background: transparent; border: none; color: #5b6472; padding: 6px 10px; }
QPushButton#ghost:hover { color: #2563eb; background: #eef3fd; }
QLineEdit, QDateEdit, QComboBox {
    background: #ffffff; border: 1px solid #d7deea; border-radius: 7px;
    padding: 6px 10px;
    selection-background-color: #cfe0ff; selection-color: #10305e;
}
QLineEdit:hover, QDateEdit:hover, QComboBox:hover { border-color: #b9c2d2; }
QLineEdit:focus, QDateEdit:focus, QComboBox:focus { border: 1px solid #2563eb; }
QDateEdit::drop-down, QComboBox::drop-down { border: none; width: 22px; }
QTableWidget {
    background: #ffffff; border: 1px solid #e3e8f0; border-radius: 10px;
    gridline-color: #eef2f7; alternate-background-color: #fbfcfe;
    selection-background-color: #dbeafe; selection-color: #10305e;
}
QTableWidget::item { padding: 3px 6px; }
QTableWidget::item:selected { background: #dbeafe; color: #10305e; }
QHeaderView::section {
    background: #f6f8fc; color: #4b5563; padding: 8px 6px;
    border: none; border-right: 1px solid #eef2f7; border-bottom: 1px solid #e3e8f0;
    font-weight: 600;
}
QTableCornerButton::section { background: #f6f8fc; border: none; }
QLabel#pageTitle { font-size: 19px; font-weight: 700; color: #111827; }
QLabel#fieldLabel { color: #4b5563; font-weight: 600; }
QLabel#muted { color: #6b7280; }
QStatusBar { background: #ffffff; border-top: 1px solid #e3e8f0; color: #5b6472; }
QStatusBar::item { border: none; }
QSplitter::handle { background: #e3e8f0; }
QScrollBar:vertical { background: transparent; width: 11px; margin: 2px; }
QScrollBar::handle:vertical { background: #cdd5e1; border-radius: 5px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: #aeb9c9; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 11px; margin: 2px; }
QScrollBar::handle:horizontal { background: #cdd5e1; border-radius: 5px; min-width: 28px; }
QScrollBar::handle:horizontal:hover { background: #aeb9c9; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QToolTip {
    background: #1f2937; color: #ffffff; border: none;
    padding: 5px 8px; border-radius: 4px;
}
"""


def apply_theme(app):
    """统一外观：Fusion 保证各家 Windows 上渲染一致，QSS 负责配色。"""
    app.setStyle("Fusion")
    app.setStyleSheet(THEME_QSS)


_ocr = None
_ocr_lock = threading.Lock()


def get_ocr():
    global _ocr
    with _ocr_lock:
        if _ocr is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
            except Exception as e:
                raise RuntimeError("未安装OCR组件 rapidocr_onnxruntime，请先运行“安装依赖.bat”后再试。\n错误信息：" + str(e))
            _ocr = RapidOCR()
    return _ocr


def clean_text(t):
    full = "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ０１２３４５６７８９"
    half = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    t = re.sub(r"[\s·.．,，\-]", "", str(t or ""))
    return t.translate(str.maketrans(full, half)).upper()


def norm_plate(s):
    return clean_text(s).replace("O", "0").replace("I", "1")


def valid_phone(s):
    s = str(s or "").strip()
    if not s:
        return True
    return bool(re.fullmatch(r"\d{11}", s))


def valid_id(s):
    s = str(s or "").strip()
    if not s:
        return True
    return bool(re.fullmatch(r"\d{17}[\dXx]", s)) or bool(re.fullmatch(r"\d{6}\*{8}\d{4}", s))


def num_of(s):
    if not s:
        return None
    m = NUM_RE.search(str(s).replace(" ", ""))
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def clean_time(t):
    m = TIME_RE.search(str(t))
    if m:
        raw = m.group(1)
        raw = raw.replace("年", "-").replace("/", "-").replace(".", "-")
        raw = raw.replace("月", "-").replace("日", " ")
        return re.sub(r"\s+", " ", raw).strip()
    m = TIME_SHORT_RE.search(str(t))
    if m:
        return m.group(1)
    return str(t).strip()[:19]


def ocr_lines(path):
    ocr = get_ocr()
    res = ocr(path)
    items = res[0] if isinstance(res, (tuple, list)) and res and isinstance(res[0], (tuple, list)) else res
    lines = []
    for it in items or []:
        try:
            box, text = it[0], str(it[1]).strip()
        except Exception:
            continue
        if not text:
            continue
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        lines.append({
            "x": min(xs), "y": min(ys),
            "cx": sum(xs) / 4.0, "cy": sum(ys) / 4.0,
            "w": max(xs) - min(xs), "h": max(ys) - min(ys),
            "text": text,
        })
    lines.sort(key=lambda l: (l["y"], l["x"]))
    return lines


def group_rows(lines):
    rows = []
    for ln in lines:
        placed = False
        for row in rows:
            if abs(ln["cy"] - row["cy"]) < max(42.0, row["h"] * 0.8):
                row["items"].append(ln)
                row["cy"] = (row["cy"] + ln["cy"]) / 2.0
                row["h"] = max(row["h"], ln["h"])
                placed = True
                break
        if not placed:
            rows.append({"items": [ln], "cy": ln["cy"], "h": ln["h"]})
    for row in rows:
        row["items"].sort(key=lambda i: i["x"])
    rows.sort(key=lambda r: r["cy"])
    return rows


def label_value(rows, labels):
    for ri, row in enumerate(rows):
        for idx, it in enumerate(row["items"]):
            t = it["text"]
            for lab in labels:
                if lab in t:
                    right = [x["text"] for x in row["items"][idx + 1:] if x["x"] > it["x"]]
                    if right:
                        return "".join(right).strip()
                    suf = t.split(lab, 1)[1].strip().lstrip(":：")
                    if suf:
                        return suf
                    if ri + 1 < len(rows) and rows[ri + 1]["cy"] - row["cy"] < 220:
                        return "".join(x["text"] for x in rows[ri + 1]["items"]).strip()
    return None


def all_times(lines):
    ts = []
    for l in lines:
        for m in TIME_RE.finditer(l["text"]):
            ts.append(m.group(1))
    if not ts:
        for l in lines:
            for m in TIME_SHORT_RE.finditer(l["text"]):
                ts.append(m.group(1))
    return ts


def extract_info(lines, kind):
    data = {}
    rows_clean = group_rows([l for l in lines if not any(k in l["text"] for k in WATERMARK_KEYS)])
    rows_full = group_rows(lines)

    plate = label_value(rows_clean, ["车牌号", "车牌", "车号"])
    if plate:
        m = PLATE_RE.search(clean_text(plate))
        data["plate"] = m.group(0) if m else clean_text(plate)[:8]
    if not data.get("plate"):
        for l in lines:
            m = PLATE_RE.search(l["text"])
            if m:
                data["plate"] = m.group(0)
                break

    top_max_y = max((l["y"] for l in lines), default=1)
    company = None
    for l in lines:
        if l["y"] > top_max_y * 0.35:
            break
        t = l["text"]
        if any(k in t for k in COMPANY_KEYS) and not any(k in t for k in ("磅单", "详情", "计量")):
            company = t
            break
    if not company:
        ship = label_value(rows_full, ["送货单位", "承运商", "收货单位", "发货单位"])
        if ship and any(k in ship for k in COMPANY_KEYS):
            company = ship
    if company:
        data["company"] = company.strip()

    name = label_value(rows_clean, ["司机姓名", "驾驶员", "司机"])
    if name and not re.search(r"\d", name) and len(name) <= 8:
        data["name"] = name

    idv = label_value(rows_clean, ["身份证号", "身份证"])
    if idv:
        idv = idv.replace(" ", "")
        if len(idv) >= 15:
            data["idcard"] = idv[:18]
    if not data.get("idcard"):
        for l in lines:
            m = ID_RE.search(l["text"])
            if m:
                data["idcard"] = m.group(0)
                break

    ph = label_value(rows_clean, ["司机电话", "联系电话", "手机号", "手机", "电话"])
    if ph:
        m = PHONE_RE.search(ph.replace(" ", ""))
        if m:
            data["phone"] = m.group(0)
    if not data.get("phone"):
        for l in lines:
            m = PHONE_RE.search(l["text"].replace(" ", ""))
            if m:
                data["phone"] = m.group(0)
                break

    mao = num_of(label_value(rows_clean, ["毛重"]))
    pi = num_of(label_value(rows_clean, ["皮重"]))
    jing = num_of(label_value(rows_clean, ["净重", "结算重量"]))
    weight = jing if jing is not None else (round(mao - pi, 2) if (mao is not None and pi is not None) else None)
    if weight is not None:
        data["weight"] = f"{weight:g}"

    if kind == "load":
        t = label_value(rows_clean, ["重车时间", "装车时间", "出厂时间", "出场时间"])
        if not t:
            times = all_times(lines)
            t = times[1] if len(times) >= 2 else (times[0] if times else None)
        if t:
            data["load_time"] = clean_time(t)
    else:
        t = label_value(rows_clean, ["二次过磅", "二磅时间", "二次磅", "空车时间", "卸货时间", "出厂时间", "出场时间"])
        if not t:
            times = all_times(lines)
            t = times[1] if len(times) >= 2 else (times[0] if times else None)
        if t:
            data["unload_time"] = clean_time(t)

    for l in lines:
        if ("新能源" in l["text"]) or ("电动" in l["text"]) or ("纯电" in l["text"]):
            data["ev"] = "电车"
            break
    return data


def auto_status(row):
    if row[2] and row[1]:
        row[8] = "完成"
    elif row[2]:
        row[8] = "卸货"
    elif row[1]:
        row[8] = "装车"
    else:
        row[8] = "准备"


def day_file(d):
    return os.path.join(DAILY_DIR, d.isoformat() + ".csv")


def read_csv(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8-sig", newline="") as f:
        for i, line in enumerate(csv.reader(f)):
            if i == 0:
                continue
            row = (line + [""] * len(DAILY_HEADER))[:len(DAILY_HEADER)]
            row = [str(x).strip() for x in row]
            if any(row):
                rows.append(row)
    return rows


def write_csv(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    backup_file(path)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for row in rows:
            w.writerow(row)


def backup_file(path):
    if not os.path.exists(path):
        return
    bdir = os.path.join(os.path.dirname(path), "备份")
    os.makedirs(bdir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(path))[0]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(path, os.path.join(bdir, f"{stem}_{ts}.csv"))
    keep = sorted([f for f in os.listdir(bdir) if f.startswith(stem + "_")])
    # 有了定时自动保存后写盘变频繁，保留 20 份（约 20 分钟内的修改历史）
    for old in keep[:-20]:
        try:
            os.remove(os.path.join(bdir, old))
        except OSError:
            pass


class ComboDelegate(QStyledItemDelegate):
    def __init__(self, options, parent=None):
        super().__init__(parent)
        self.options = options

    def createEditor(self, parent, option, index):
        cb = QComboBox(parent)
        cb.addItems(self.options)
        return cb

    def setEditorData(self, editor, index):
        editor.setCurrentText(str(index.data() or ""))

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), Qt.EditRole)


class DropZone(QFrame):
    filesDropped = Signal(list)

    def __init__(self, title, hint, color, bg="#f8fafc", bg_hover="#f1f6ff", parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(122)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            "QFrame { border: 2px dashed %s; border-radius: 12px; background: %s; }"
            "QFrame:hover { border-color: %s; background: %s; }"
            % (color, bg, color, bg_hover)
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(7)
        t = QLabel(title)
        t.setStyleSheet("color:%s; font-size:15px; font-weight:700; border:none; background:transparent;" % color)
        t.setAlignment(Qt.AlignCenter)
        h = QLabel(hint)
        h.setStyleSheet("color:#7b8494; border:none; background:transparent;")
        h.setAlignment(Qt.AlignCenter)
        lay.addStretch(1)
        lay.addWidget(t)
        lay.addWidget(h)
        lay.addStretch(1)

    def dragEnterEvent(self, e):
        m = e.mimeData()
        if m.hasUrls() or m.hasImage():
            e.acceptProposedAction()
        else:
            e.ignore()

    def dropEvent(self, e):
        m = e.mimeData()
        paths = []
        if m.hasUrls():
            for url in m.urls():
                p = url.toLocalFile()
                if p:
                    paths.append(p)
        elif m.hasImage():
            img = m.imageData()
            if img and isinstance(img, QImage) and not img.isNull():
                fd, tmp = tempfile.mkstemp(suffix=".png")
                os.close(fd)
                img.save(tmp, "PNG")
                paths.append(tmp)
        if paths:
            self.filesDropped.emit(paths)
        e.acceptProposedAction()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            paths, _ = QFileDialog.getOpenFileNames(
                self, "选择截图（可按住Ctrl多选）", "",
                "图片文件 (*.jpg *.jpeg *.png *.bmp *.webp);;所有文件 (*.*)")
            if paths:
                self.filesDropped.emit(paths)


class OCRThread(QThread):
    done = Signal(dict)
    failed = Signal(str)

    def __init__(self, path, kind, parent=None):
        super().__init__(parent)
        self.path = path
        self.kind = kind

    def run(self):
        try:
            lines = ocr_lines(self.path)
            data = extract_info(lines, self.kind)
            self.done.emit(data)
        except Exception as e:
            self.failed.emit(str(e))


class ExtractDialog(QDialog):
    def __init__(self, kind, data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("识别结果确认")
        self.setMinimumWidth(430)
        lay = QVBoxLayout(self)
        if kind == "load":
            info = QLabel("识别出的装车信息如下，可修改后确认导入。\n将按车牌号匹配当日信息表：已存在则补充，不存在则新增一行。")
        else:
            info = QLabel("识别出的卸货信息如下，可修改后确认导入。\n若车牌号已在当日信息表：直接补充；若在前一天的信息表：先复制其已填数据到今天，再补充卸货信息。")
        info.setWordWrap(True)
        lay.addWidget(info)
        form = QFormLayout()
        self._fields = {}
        if kind == "load":
            pairs = [("车牌号", "plate"), ("装车时间", "load_time"), ("装车净重", "weight")]
        else:
            pairs = [("车牌号", "plate"), ("卸货时间", "unload_time"), ("卸货净重", "weight")]
        pairs += [("身份证号", "idcard"), ("司机姓名", "name"), ("司机电话", "phone"), ("抬头", "company"), ("电车or油车", "ev")]
        for label, key in pairs:
            if key == "ev":
                cb = QComboBox()
                cb.addItems(["", "电车", "油车"])
                cur = data.get(key) or ""
                if cur not in ("电车", "油车"):
                    cur = ""
                cb.setCurrentText(cur)
                self._fields[key] = cb
                form.addRow(label, cb)
            else:
                le = QLineEdit(str(data.get(key) or ""))
                le.setMinimumWidth(320)
                self._fields[key] = le
                form.addRow(label, le)
        lay.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("确认导入")
        bb.button(QDialogButtonBox.Cancel).setText("取消")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def get_data(self):
        d = {}
        for k, w in self._fields.items():
            if isinstance(w, QLineEdit):
                v = w.text().strip()
                if v:
                    d[k] = v
            else:
                v = w.currentText().strip()
                if v:
                    d[k] = v
        if d.get("plate"):
            d["plate"] = clean_text(d["plate"])
        return d


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("车辆管理系统")
        # 自适应窗口：小屏笔记本也不会把按钮顶出屏幕，并居中显示
        _scr = QApplication.primaryScreen()
        if _scr is not None:
            _g = _scr.availableGeometry()
            self.resize(min(1420, int(_g.width() * 0.92)), min(820, int(_g.height() * 0.92)))
        else:
            self.resize(1420, 820)
        self.setMinimumSize(1000, 620)
        if _scr is not None:
            self.move(_g.x() + max(0, (_g.width() - self.width()) // 2),
                      _g.y() + max(0, (_g.height() - self.height()) // 2))
        self.current_date = date.today()
        self.day_rows = []
        self.driver_rows = []
        self._guard = True
        self._guard2 = True
        self._date_guard = False
        self._ocr_busy = False
        self._queue = []
        self._queue_total = 0
        self._thread = None
        self._progress = None
        self._temp_path = None
        self._build_ui()
        self.load_day_rows()
        self.load_driver_rows()
        # 定时自动保存：60 秒检查一次，内容有变化才写盘
        self._autosave = QTimer(self)
        self._autosave.setInterval(60 * 1000)
        self._autosave.timeout.connect(self.auto_save)
        self._autosave.start()

    def _build_ui(self):
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        self.setCentralWidget(tabs)
        tabs.addTab(self._build_day_tab(), "当日信息表")
        tabs.addTab(self._build_driver_tab(), "司机身份登记表")
        welcome = "欢迎使用车辆管理系统"
        if DATA_IS_FALLBACK:
            welcome += f"　（程序目录不可写，数据已存到 {DATA_DIR}）"
        self.statusBar().showMessage(welcome)
        self.statusBar().setSizeGripEnabled(False)
        loc = QLabel(f"数据目录：{DATA_DIR}")
        loc.setObjectName("muted")
        self.statusBar().addPermanentWidget(loc)

    def _mkbtn(self, text, fn, kind=None):
        b = QPushButton(text)
        if kind:
            b.setObjectName(kind)
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(fn)
        return b

    @staticmethod
    def _mkfield(text):
        lb = QLabel(text)
        lb.setObjectName("fieldLabel")
        return lb

    @staticmethod
    def _style_table(tbl):
        """表格的视觉：无网格线、隔行变色、行高 30、表头浅灰。"""
        tbl.setAlternatingRowColors(True)
        tbl.setShowGrid(False)
        tbl.setWordWrap(False)
        tbl.verticalHeader().setDefaultSectionSize(30)
        tbl.verticalHeader().setDefaultAlignment(Qt.AlignCenter)
        tbl.horizontalHeader().setHighlightSections(False)
        tbl.horizontalHeader().setFixedHeight(34)

    def _build_day_tab(self):
        w = QWidget()
        w.setObjectName("tabPage")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(11)

        top = QHBoxLayout()
        top.setSpacing(8)
        self.title_label = QLabel()
        self.title_label.setObjectName("pageTitle")
        top.addWidget(self.title_label)
        top.addStretch(1)
        top.addWidget(self._mkfield("日期："))
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setDate(self.current_date)
        self.date_edit.dateChanged.connect(self.on_date_changed)
        top.addWidget(self.date_edit)
        top.addSpacing(4)
        for text, fn in (("◀ 前一天", self.prev_day), ("后一天 ▶", self.next_day), ("今天", self.today)):
            top.addWidget(self._mkbtn(text, fn))
        top.addSpacing(6)
        top.addWidget(self._mkbtn("打开数据文件夹", self.open_data_dir, "ghost"))
        lay.addLayout(top)

        drops = QHBoxLayout()
        drops.setSpacing(12)
        self.zone_load = DropZone("装车截图上传入口", "把微信中的装车截图（磅单详情）拖到这里（可一次拖入多张），或点击选择文件（可Ctrl多选）\n自动提取：车牌号、重车时间、净重、司机信息、抬头", "#1a7f37", "#f4fbf6", "#e9f8ef")
        self.zone_unload = DropZone("卸货截图上传入口", "把微信中的卸货截图（物资计量单）拖到这里（可一次拖入多张），或点击选择文件（可Ctrl多选）\n自动提取：车牌号、二次过磅时间、净重、司机信息、抬头", "#1f5fbf", "#f4f8ff", "#e8f0ff")
        self.zone_load.filesDropped.connect(lambda ps: self.on_zone_files("load", ps))
        self.zone_unload.filesDropped.connect(lambda ps: self.on_zone_files("unload", ps))
        drops.addWidget(self.zone_load)
        drops.addWidget(self.zone_unload)
        lay.addLayout(drops)

        search = QHBoxLayout()
        search.setSpacing(8)
        search.addWidget(self._mkfield("查询："))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("输入任意键查询（车牌号、省份如 晋/沪、司机姓名、电话、身份证号…）")
        self.search_edit.textChanged.connect(self.refresh_search)
        search.addWidget(self.search_edit, 1)
        search.addWidget(self._mkbtn("清除", lambda: self.search_edit.clear(), "ghost"))
        lay.addLayout(search)

        btns = QHBoxLayout()
        btns.setSpacing(8)
        btns.addWidget(self._mkbtn("新增行", self.add_row))
        btns.addWidget(self._mkbtn("删除选中行", self.del_row, "danger"))
        btns.addWidget(self._mkbtn("保存当日表", self.save_day_rows, "primary"))
        btns.addWidget(self._mkbtn("导出Excel", self.export_day_xlsx))
        btns.addStretch(1)
        btns.addWidget(self._mkbtn("打开车辆运货统计表", self.open_stats, "accent"))
        lay.addLayout(btns)

        self.day_table = QTableWidget(0, len(DAILY_HEADER))
        self.day_table.setHorizontalHeaderLabels(DAILY_HEADER)
        self.day_table.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)
        for c, wd in enumerate(COL_W):
            self.day_table.setColumnWidth(c, wd)
        self.day_table.horizontalHeader().setSectionResizeMode(len(DAILY_HEADER) - 1, QHeaderView.Stretch)
        self.day_table.setItemDelegateForColumn(8, ComboDelegate(["", "准备", "装车", "卸货", "完成"]))
        self.day_table.setItemDelegateForColumn(9, ComboDelegate(["", "电车", "油车"]))
        self.day_table.itemChanged.connect(self.on_day_item_changed)
        self._style_table(self.day_table)
        lay.addWidget(self.day_table, 1)
        return w

    def _build_driver_tab(self):
        w = QWidget()
        w.setObjectName("tabPage")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(11)
        search = QHBoxLayout()
        search.setSpacing(8)
        search.addWidget(self._mkfield("查询："))
        self.driver_search = QLineEdit()
        self.driver_search.setPlaceholderText("输入身份证号、司机姓名、电话号、车牌号等任意键，定位司机身份")
        self.driver_search.textChanged.connect(self.refresh_driver_search)
        search.addWidget(self.driver_search, 1)
        search.addWidget(self._mkbtn("清除", lambda: self.driver_search.clear(), "ghost"))
        lay.addLayout(search)
        btns = QHBoxLayout()
        btns.setSpacing(8)
        btns.addWidget(self._mkbtn("新增行", self.add_driver_row))
        btns.addWidget(self._mkbtn("删除选中行", self.del_driver_row, "danger"))
        btns.addWidget(self._mkbtn("保存登记表", self.save_driver_rows, "primary"))
        btns.addWidget(self._mkbtn("导出Excel", self.export_driver_xlsx))
        btns.addStretch(1)
        btns.addWidget(self._mkbtn("从每日信息导入司机", self.import_drivers, "accent"))
        lay.addLayout(btns)
        self.driver_table = QTableWidget(0, len(DRIVER_HEADER))
        self.driver_table.setHorizontalHeaderLabels(DRIVER_HEADER)
        self.driver_table.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)
        for c, wd in enumerate([190, 110, 130, 300]):
            self.driver_table.setColumnWidth(c, wd)
        self.driver_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.driver_table.itemChanged.connect(self.on_driver_item_changed)
        self._style_table(self.driver_table)
        lay.addWidget(self.driver_table, 1)
        return w

    def load_day_rows(self):
        self.day_rows = read_csv(day_file(self.current_date))
        self.populate_table()

    def populate_table(self):
        self._guard = True
        tbl = self.day_table
        tbl.setRowCount(len(self.day_rows))
        for r, row in enumerate(self.day_rows):
            for c, val in enumerate(row):
                item = QTableWidgetItem(str(val or ""))
                item.setTextAlignment(Qt.AlignCenter)
                item.setData(Qt.UserRole, val or "")
                tbl.setItem(r, c, item)
        self._guard = False
        self.title_label.setText(f"{self.current_date.year}年{self.current_date.month}月{self.current_date.day}日装车信息表")
        self.refresh_search()

    def collect_rows(self):
        rows = []
        tbl = self.day_table
        for r in range(tbl.rowCount()):
            row = []
            for c in range(len(DAILY_HEADER)):
                it = tbl.item(r, c)
                row.append(it.text().strip() if it else "")
            if any(row):
                rows.append(row)
        return rows

    def save_day_rows(self):
        rows = self.collect_rows()
        self.day_rows = rows
        write_csv(day_file(self.current_date), DAILY_HEADER, rows)
        self.statusBar().showMessage(f"已保存：{day_file(self.current_date)}", 5000)

    def sync_from_table(self):
        """把表格里当前的编辑收回 self.day_rows。

        populate_table() 是按 self.day_rows 重建表格的，而单元格编辑只写在
        QTableWidgetItem 上、不写回 self.day_rows。若重建前不同步，界面上
        未保存的手改会被旧值覆盖，随后 save_day_rows() 再把旧值写进磁盘。
        """
        self.day_rows = self.collect_rows()

    def auto_save(self):
        """定时自动保存，内容没变化时跳过，避免无意义地刷备份。"""
        rows = self.collect_rows()
        if rows != self.day_rows:
            try:
                self.day_rows = rows
                write_csv(day_file(self.current_date), DAILY_HEADER, rows)
                self.statusBar().showMessage(f"已自动保存 {datetime.now().strftime('%H:%M:%S')}", 4000)
            except Exception as e:
                self.statusBar().showMessage(f"自动保存失败：{e}", 8000)
        drows = self.collect_driver_rows()
        ids = [r[0] for r in drows if r[0]]
        if drows != self.driver_rows and len(set(ids)) == len(ids):
            try:
                self.driver_rows = drows
                write_csv(DRIVER_FILE, DRIVER_HEADER, drows)
            except Exception:
                pass

    def on_date_changed(self, qd):
        if self._date_guard:
            return
        self.save_day_rows()
        self.current_date = qd.toPython()
        self.load_day_rows()

    def prev_day(self):
        self.date_edit.setDate(self.date_edit.date().addDays(-1))

    def next_day(self):
        self.date_edit.setDate(self.date_edit.date().addDays(1))

    def today(self):
        self.date_edit.setDate(date.today())

    def open_data_dir(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        os.startfile(DATA_DIR)

    def open_stats(self):
        if getattr(sys, "frozen", False):
            stats = os.path.join(APP_DIR, "车辆运货统计表.exe")
            if not os.path.exists(stats):
                QMessageBox.warning(self, "提示", "未找到 车辆运货统计表.exe，请确认与主程序在同一文件夹。")
                return
            try:
                subprocess.Popen([stats, DATA_DIR])
            except Exception as e:
                QMessageBox.warning(self, "提示", "打开失败：" + str(e))
            return
        if not os.path.exists(STATS_APP):
            QMessageBox.warning(self, "提示", "未找到 车辆运货统计表.py 文件，请确认与主程序在同一文件夹。")
            return
        flags = 0x08000000 if os.name == "nt" else 0
        try:
            subprocess.Popen([sys.executable, STATS_APP, DATA_DIR], creationflags=flags)
        except Exception as e:
            QMessageBox.warning(self, "提示", "打开失败：" + str(e))

    def add_row(self):
        self.sync_from_table()
        self.day_rows.append([""] * len(DAILY_HEADER))
        self.populate_table()
        self.save_day_rows()

    def del_row(self):
        rows = self.day_table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "提示", "请先选中要删除的行。")
            return
        # 直接从表格删，再回收内容，避免空行导致下标错位
        for idx in sorted((i.row() for i in rows), reverse=True):
            self.day_table.removeRow(idx)
        self.sync_from_table()
        self.populate_table()
        self.save_day_rows()

    def refresh_search(self):
        q = self.search_edit.text().strip() if hasattr(self, "search_edit") else ""
        tbl = self.day_table
        shown = 0
        for r in range(tbl.rowCount()):
            row = [tbl.item(r, c).text() if tbl.item(r, c) else "" for c in range(len(DAILY_HEADER))]
            ok = self.match_row(q, row)
            tbl.setRowHidden(r, not ok)
            if ok:
                shown += 1
        self.statusBar().showMessage(f"当前显示 {shown} / {tbl.rowCount()} 条记录　文件：{day_file(self.current_date)}")

    def match_row(self, q, row):
        if not q:
            return True
        if len(q) == 1 and q in PLATE_PROV:
            return clean_text(row[0]).startswith(q)
        if q[0] in PLATE_PROV and 1 < len(q) <= 7 and re.fullmatch(r"[A-Za-z0-9·.]+", q[1:]):
            return norm_plate(row[0]).startswith(norm_plate(q))
        ql = q.lower()
        for v in row:
            if ql in str(v).lower():
                return True
        return False

    def on_day_item_changed(self, item):
        if self._guard:
            return
        col = item.column()
        val = item.text()
        if col == 5 and not valid_id(val):
            QMessageBox.warning(self, "格式错误", "身份证号应为18位（17位数字 + 1位数字或字母X）。")
            self._revert_item(item)
            return
        if col == 7 and not valid_phone(val):
            QMessageBox.warning(self, "格式错误", "司机电话应为11位数字。")
            self._revert_item(item)
            return
        item.setData(Qt.UserRole, val)

    def _revert_item(self, item):
        self._guard = True
        item.setText(str(item.data(Qt.UserRole) or ""))
        self._guard = False

    def export_day_xlsx(self):
        try:
            from openpyxl import Workbook
        except Exception:
            QMessageBox.information(self, "提示", "未安装 openpyxl，请先运行“安装依赖.bat”。")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出Excel",
            os.path.join(DAILY_DIR, f"{self.current_date.isoformat()}_装车信息表.xlsx"),
            "Excel文件 (*.xlsx)")
        if not path:
            return
        wb = Workbook()
        ws = wb.active
        ws.title = "装车信息表"
        ws.append(DAILY_HEADER)
        for row in self.collect_rows():
            ws.append(row)
        wb.save(path)
        QMessageBox.information(self, "完成", "已导出：" + path)

    def on_zone_files(self, kind, paths):
        if self._ocr_busy:
            QMessageBox.information(self, "请稍候", "正在识别截图，请稍候…")
            return
        valid, dats = [], []
        for p in paths:
            if p.lower().endswith(".dat"):
                dats.append(p)
            elif os.path.exists(p):
                valid.append(p)
        if dats:
            QMessageBox.warning(self, "已跳过加密文件", "微信聊天中的 .dat 是加密文件，无法直接识别，已跳过 " + str(len(dats)) + " 个。\n请先在微信中把图片“另存为”到电脑，再拖入保存后的图片文件。")
        if not valid:
            return
        self._queue = [(kind, p) for p in valid]
        self._queue_total = len(valid)
        self._process_next()

    def _process_next(self):
        if not self._queue:
            self._ocr_busy = False
            self.statusBar().showMessage("截图批量导入完成", 6000)
            return
        kind, path = self._queue.pop(0)
        self._ocr_busy = True
        done = self._queue_total - len(self._queue)
        self._temp_path = path if path.startswith(tempfile.gettempdir()) else None
        self._progress = QProgressDialog(
            f"正在识别第 {done} / {self._queue_total} 张截图，请稍候…", "", 0, 0, self)
        self._progress.setWindowTitle("OCR识别")
        self._progress.setWindowModality(Qt.WindowModal)
        self._progress.setCancelButton(None)
        self._progress.setMinimumDuration(200)
        self._progress.show()
        self._thread = OCRThread(path, kind)
        self._thread.done.connect(lambda data, k=kind: self.on_ocr_done(k, data))
        self._thread.failed.connect(self.on_ocr_failed)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _close_progress(self):
        if self._progress:
            self._progress.close()
            self._progress = None
        if self._temp_path and os.path.exists(self._temp_path):
            try:
                os.remove(self._temp_path)
            except OSError:
                pass
        self._temp_path = None

    def on_ocr_done(self, kind, data):
        self._close_progress()
        if not any(data.values()):
            QMessageBox.warning(self, "识别结果", f"第 {self._queue_total - len(self._queue)} 张未识别到有效文字信息，已跳过。")
            self._process_next()
            return
        dlg = ExtractDialog(kind, data, self)
        if dlg.exec() == QDialog.Accepted:
            self.apply_extract(kind, dlg.get_data())
        self._process_next()

    def on_ocr_failed(self, msg):
        self._close_progress()
        QMessageBox.warning(self, "识别失败", f"第 {self._queue_total - len(self._queue)} 张识别失败：{msg}")
        self._process_next()

    def apply_extract(self, kind, data):
        self.sync_from_table()
        rows = self.day_rows
        plate = norm_plate(data.get("plate") or "")
        idx = None
        if plate:
            for i, r in enumerate(rows):
                if norm_plate(r[0]) == plate:
                    idx = i
                    break
        note = "新增记录"
        if kind == "unload" and idx is None and plate:
            yrows = read_csv(day_file(self.current_date - timedelta(days=1)))
            for yr in yrows:
                if norm_plate(yr[0]) == plate:
                    rows.append(list(yr))
                    idx = len(rows) - 1
                    note = "已复制前一天数据并补充卸货信息"
                    break
        if idx is None:
            rows.append([""] * len(DAILY_HEADER))
            idx = len(rows) - 1
        else:
            note = "已合并到当日已有记录"
        row = rows[idx]
        if kind == "load":
            if data.get("plate"):
                row[0] = data["plate"]
            if data.get("load_time"):
                row[1] = data["load_time"]
            if data.get("weight"):
                row[3] = data["weight"]
        else:
            if data.get("plate"):
                row[0] = data["plate"]
            if data.get("unload_time"):
                row[2] = data["unload_time"]
            if data.get("weight"):
                row[4] = data["weight"]
        for col, key in ((5, "idcard"), (6, "name"), (7, "phone"), (10, "company"), (9, "ev")):
            if data.get(key) and not row[col]:
                row[col] = data[key]
        auto_status(row)
        self.populate_table()
        self.save_day_rows()
        self.statusBar().showMessage(f"导入成功：{row[0] or '未识别车牌'}（{note}）", 8000)

    def load_driver_rows(self):
        rows = []
        if os.path.exists(DRIVER_FILE):
            with open(DRIVER_FILE, encoding="utf-8-sig", newline="") as f:
                for i, line in enumerate(csv.reader(f)):
                    if i == 0:
                        continue
                    row = (line + [""] * len(DRIVER_HEADER))[:len(DRIVER_HEADER)]
                    row = [str(x).strip() for x in row]
                    if any(row):
                        rows.append(row)
        self.driver_rows = rows
        self.populate_driver_table()

    def populate_driver_table(self):
        self._guard2 = True
        tbl = self.driver_table
        tbl.setRowCount(len(self.driver_rows))
        for r, row in enumerate(self.driver_rows):
            for c, val in enumerate(row):
                item = QTableWidgetItem(str(val or ""))
                item.setTextAlignment(Qt.AlignCenter)
                item.setData(Qt.UserRole, val or "")
                tbl.setItem(r, c, item)
        self._guard2 = False
        self.refresh_driver_search()

    def collect_driver_rows(self):
        rows = []
        tbl = self.driver_table
        for r in range(tbl.rowCount()):
            row = []
            for c in range(len(DRIVER_HEADER)):
                it = tbl.item(r, c)
                row.append(it.text().strip() if it else "")
            if any(row):
                rows.append(row)
        return rows

    def sync_driver_table(self):
        """同 sync_from_table，司机表格的未保存手改也先收回 driver_rows。"""
        self.driver_rows = self.collect_driver_rows()

    def save_driver_rows(self):
        rows = self.collect_driver_rows()
        seen = {}
        for row in rows:
            if row[0] and row[0] in seen:
                QMessageBox.warning(self, "保存失败", f"身份证号重复（主键唯一）：{row[0]}\n请修改后再保存。")
                return False
            seen[row[0]] = True
        self.driver_rows = rows
        write_csv(DRIVER_FILE, DRIVER_HEADER, rows)
        self.statusBar().showMessage(f"已保存：{DRIVER_FILE}", 5000)
        return True

    def add_driver_row(self):
        self.sync_driver_table()
        self.driver_rows.append([""] * len(DRIVER_HEADER))
        self.populate_driver_table()
        self.save_driver_rows()

    def del_driver_row(self):
        rows = self.driver_table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "提示", "请先选中要删除的行。")
            return
        for idx in sorted((i.row() for i in rows), reverse=True):
            self.driver_table.removeRow(idx)
        self.sync_driver_table()
        self.populate_driver_table()
        self.save_driver_rows()

    def refresh_driver_search(self):
        q = self.driver_search.text().strip() if hasattr(self, "driver_search") else ""
        tbl = self.driver_table
        shown = 0
        for r in range(tbl.rowCount()):
            row = [tbl.item(r, c).text() if tbl.item(r, c) else "" for c in range(len(DRIVER_HEADER))]
            ok = (not q) or any(q.lower() in str(v).lower() for v in row)
            tbl.setRowHidden(r, not ok)
            if ok:
                shown += 1
        self.statusBar().showMessage(f"司机登记：显示 {shown} / {tbl.rowCount()} 条")

    def on_driver_item_changed(self, item):
        if self._guard2:
            return
        col = item.column()
        val = item.text()
        if col == 0 and not valid_id(val):
            QMessageBox.warning(self, "格式错误", "身份证号应为18位（17位数字 + 1位数字或字母X）。")
            self._revert_driver_item(item)
            return
        if col == 2 and not valid_phone(val):
            QMessageBox.warning(self, "格式错误", "司机电话应为11位数字。")
            self._revert_driver_item(item)
            return
        item.setData(Qt.UserRole, val)

    def _revert_driver_item(self, item):
        self._guard2 = True
        item.setText(str(item.data(Qt.UserRole) or ""))
        self._guard2 = False

    def export_driver_xlsx(self):
        try:
            from openpyxl import Workbook
        except Exception:
            QMessageBox.information(self, "提示", "未安装 openpyxl，请先运行“安装依赖.bat”。")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出Excel",
            os.path.join(DATA_DIR, "司机身份登记表.xlsx"),
            "Excel文件 (*.xlsx)")
        if not path:
            return
        wb = Workbook()
        ws = wb.active
        ws.title = "司机身份登记表"
        ws.append(DRIVER_HEADER)
        for row in self.collect_driver_rows():
            ws.append(row)
        wb.save(path)
        QMessageBox.information(self, "完成", "已导出：" + path)

    def import_drivers(self):
        dmap = {}
        if os.path.isdir(DAILY_DIR):
            for fn in sorted(os.listdir(DAILY_DIR)):
                if not fn.endswith(".csv"):
                    continue
                for row in read_csv(os.path.join(DAILY_DIR, fn)):
                    idv, name, phone, plate = row[5], row[6], row[7], row[0]
                    if not idv:
                        continue
                    rec = dmap.setdefault(idv, {"name": "", "phone": "", "plates": []})
                    if name and not rec["name"]:
                        rec["name"] = name
                    if phone and not rec["phone"]:
                        rec["phone"] = phone
                    if plate and plate not in rec["plates"]:
                        rec["plates"].append(plate)
        if not dmap:
            QMessageBox.information(self, "提示", "每日信息表中暂无可导入的司机信息（需有身份证号）。")
            return
        existing = {}
        self.sync_driver_table()
        for row in self.driver_rows:
            if row[0]:
                existing[row[0]] = row
        for idv, rec in dmap.items():
            if idv in existing:
                row = existing[idv]
                if not row[1] and rec["name"]:
                    row[1] = rec["name"]
                if not row[2] and rec["phone"]:
                    row[2] = rec["phone"]
                plates = [p for p in re.split(r"[,，;；]", row[3]) if p.strip()]
                for p in rec["plates"]:
                    if p not in plates:
                        plates.append(p)
                row[3] = "，".join(plates)
            else:
                self.driver_rows.append([idv, rec["name"], rec["phone"], "，".join(rec["plates"])])
        self.populate_driver_table()
        self.save_driver_rows()
        QMessageBox.information(self, "完成", f"已导入/合并 {len(dmap)} 位司机身份信息。")

    def closeEvent(self, event):
        try:
            self.save_day_rows()
            self.save_driver_rows()
        except Exception:
            pass
        event.accept()


def _log_exception(exc_type, exc_value, tb):
    msg = "".join(traceback.format_exception(exc_type, exc_value, tb))
    try:
        with open(os.path.join(APP_DIR, "运行错误日志.txt"), "a", encoding="utf-8") as f:
            f.write("\n" + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n" + msg + "\n")
    except Exception:
        pass
    try:
        QMessageBox.critical(None, "程序出错", msg[-1500:])
    except Exception:
        pass


sys.excepthook = _log_exception


def main():
    app = QApplication(sys.argv)
    apply_theme(app)
    w = MainWindow()
    w.show()
    os._exit(app.exec())


if __name__ == "__main__":
    main()
