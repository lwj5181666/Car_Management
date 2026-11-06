# -*- coding: utf-8 -*-
import csv
import os
import re
import sys
import traceback
from datetime import date, datetime, timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QDateEdit, QFileDialog, QHBoxLayout, QHeaderView,
    QLabel, QMainWindow, QMessageBox, QPushButton, QSplitter,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

DETAIL_HEADER = ["日期", "车牌号", "装车时间", "卸货时间", "装车净重", "卸货净重", "身份证号", "司机姓名", "司机电话", "目前状态", "电车or油车", "抬头"]
SUMMARY_HEADER = ["车牌号", "次数"]

# ---------------------------------------------------------------- 界面主题
# 与主程序保持同一套视觉（浅色工作台）。只影响外观，不影响计算。
THEME_QSS = """
* {
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 10pt;
    color: #1f2937;
}
QMainWindow, QDialog { background: #f3f5f9; }
QWidget#tabPage { background: #f3f5f9; }
QPushButton {
    background: #ffffff; border: 1px solid #d7deea; border-radius: 7px;
    padding: 7px 16px; color: #374151;
}
QPushButton:hover { border-color: #2563eb; color: #2563eb; background: #f8fbff; }
QPushButton:pressed { background: #eef3fd; }
QPushButton#primary {
    background: #2563eb; border: 1px solid #2563eb; color: #ffffff; font-weight: 600;
}
QPushButton#primary:hover { background: #1d4ed8; border-color: #1d4ed8; color: #ffffff; }
QPushButton#accent {
    background: #eff5ff; border: 1px solid #bcd2fb; color: #1d4ed8; font-weight: 600;
}
QPushButton#accent:hover { background: #e2edff; border-color: #2563eb; color: #1d4ed8; }
QDateEdit {
    background: #ffffff; border: 1px solid #d7deea; border-radius: 7px;
    padding: 6px 10px;
    selection-background-color: #cfe0ff; selection-color: #10305e;
}
QDateEdit:hover { border-color: #b9c2d2; }
QDateEdit:focus { border: 1px solid #2563eb; }
QDateEdit::drop-down { border: none; width: 22px; }
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
QSplitter::handle { background: #e3e8f0; height: 6px; }
QSplitter::handle:hover { background: #c9d3e2; }
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
    app.setStyle("Fusion")
    app.setStyleSheet(THEME_QSS)


def norm_plate(s):
    full = "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ０１２３４５６７８９"
    half = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    t = re.sub(r"[\s·.．,，\-]", "", str(s or "")).translate(str.maketrans(full, half)).upper()
    return t.replace("O", "0").replace("I", "1")


def _app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _pick_data_dir():
    """与主程序一致：程序旁边优先，不可写时退回 %LOCALAPPDATA%。"""
    beside = os.path.join(_app_dir(), "数据")
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


def resolve_dirs():
    if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]):
        data_dir = sys.argv[1]
    else:
        data_dir = _pick_data_dir()
    return data_dir, os.path.join(data_dir, "每日信息")


def read_rows(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8-sig", newline="") as f:
        for i, line in enumerate(csv.reader(f)):
            if i == 0:
                continue
            row = (line + [""] * 11)[:11]
            row = [str(x).strip() for x in row]
            if any(row):
                rows.append(row)
    return rows


def dedupe(records):
    out = []
    index = {}
    for rec in records:
        plate = norm_plate(rec[1])
        lt, ut = rec[2], rec[3]
        key = None
        if plate and lt:
            key = (plate, lt)
        if key and key in index:
            i = index[key]
            old = out[i]
            if (not old[3] and ut) or (old[3] and ut and rec[0] > old[0]):
                out[i] = rec
            continue
        if key:
            index[key] = len(out)
        out.append(rec)
    return out


class StatsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("车辆运货统计表")
        self.setMinimumSize(980, 600)
        _scr = QApplication.primaryScreen()
        if _scr is not None:
            _g = _scr.availableGeometry()
            self.resize(min(1380, int(_g.width() * 0.92)), min(760, int(_g.height() * 0.92)))
            self.move(_g.x() + max(0, (_g.width() - self.width()) // 2),
                      _g.y() + max(0, (_g.height() - self.height()) // 2))
        else:
            self.resize(1380, 760)
        self.data_dir, self.daily_dir = resolve_dirs()
        self._build_ui()

    def _build_ui(self):
        w = QWidget()
        w.setObjectName("tabPage")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 14, 16, 12)
        lay.setSpacing(11)

        head = QHBoxLayout()
        head.setSpacing(8)
        title = QLabel("车辆运货统计表")
        title.setObjectName("pageTitle")
        head.addWidget(title)
        head.addStretch(1)
        loc = QLabel("数据目录：" + self.data_dir)
        loc.setObjectName("muted")
        head.addWidget(loc)
        lay.addLayout(head)

        top = QHBoxLayout()
        top.setSpacing(8)
        lb1 = QLabel("开始日期：")
        lb1.setObjectName("fieldLabel")
        top.addWidget(lb1)
        self.start_edit = QDateEdit()
        self.start_edit.setCalendarPopup(True)
        self.start_edit.setDisplayFormat("yyyy-MM-dd")
        self.start_edit.setDate(date.today() - timedelta(days=30))
        top.addWidget(self.start_edit)
        lb2 = QLabel("结束日期：")
        lb2.setObjectName("fieldLabel")
        top.addWidget(lb2)
        self.end_edit = QDateEdit()
        self.end_edit.setCalendarPopup(True)
        self.end_edit.setDisplayFormat("yyyy-MM-dd")
        self.end_edit.setDate(date.today())
        top.addWidget(self.end_edit)
        top.addSpacing(6)
        bq = QPushButton("查询")
        bq.setObjectName("primary")
        bq.setCursor(Qt.PointingHandCursor)
        bq.clicked.connect(self.query)
        top.addWidget(bq)
        be = QPushButton("导出明细CSV")
        be.setObjectName("accent")
        be.setCursor(Qt.PointingHandCursor)
        be.clicked.connect(self.export_detail)
        top.addWidget(be)
        bs = QPushButton("导出汇总CSV")
        bs.setObjectName("accent")
        bs.setCursor(Qt.PointingHandCursor)
        bs.clicked.connect(self.export_summary)
        top.addWidget(bs)
        top.addStretch(1)
        lay.addLayout(top)

        self.result_label = QLabel("请输入起止时间后点击“查询”。")
        self.result_label.setStyleSheet("color:#111827; font-weight:600; padding:2px 2px;")
        lay.addWidget(self.result_label)

        split = QSplitter(Qt.Vertical)
        self.detail_table = QTableWidget(0, len(DETAIL_HEADER))
        self.detail_table.setHorizontalHeaderLabels(DETAIL_HEADER)
        self.detail_table.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)
        for c, wd in enumerate([95, 105, 160, 160, 85, 85, 175, 95, 120, 75, 80, 190]):
            self.detail_table.setColumnWidth(c, wd)
        self.detail_table.horizontalHeader().setSectionResizeMode(len(DETAIL_HEADER) - 1, QHeaderView.Stretch)
        self._style_table(self.detail_table)
        split.addWidget(self.detail_table)

        self.summary_table = QTableWidget(0, len(SUMMARY_HEADER))
        self.summary_table.setHorizontalHeaderLabels(SUMMARY_HEADER)
        self.summary_table.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)
        self.summary_table.setColumnWidth(0, 220)
        self.summary_table.setColumnWidth(1, 120)
        self.summary_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._style_table(self.summary_table)
        split.addWidget(self.summary_table)
        split.setSizes([520, 180])
        lay.addWidget(split, 1)
        self.setCentralWidget(w)

    @staticmethod
    def _style_table(tbl):
        tbl.setAlternatingRowColors(True)
        tbl.setShowGrid(False)
        tbl.setWordWrap(False)
        tbl.verticalHeader().setDefaultSectionSize(30)
        tbl.verticalHeader().setDefaultAlignment(Qt.AlignCenter)
        tbl.horizontalHeader().setHighlightSections(False)
        tbl.horizontalHeader().setFixedHeight(34)

    def query(self):
        start = self.start_edit.date().toPython()
        end = self.end_edit.date().toPython()
        if start > end:
            start, end = end, start
        records = []
        if os.path.isdir(self.daily_dir):
            for fn in sorted(os.listdir(self.daily_dir)):
                if not fn.endswith(".csv"):
                    continue
                stem = fn[:-4]
                try:
                    d = datetime.strptime(stem, "%Y-%m-%d").date()
                except ValueError:
                    continue
                if not (start <= d <= end):
                    continue
                for row in read_rows(os.path.join(self.daily_dir, fn)):
                    records.append([d.isoformat()] + row)
        records = dedupe(records)
        self.records = records

        self.detail_table.setRowCount(len(records))
        for r, rec in enumerate(records):
            for c, val in enumerate(rec):
                item = QTableWidgetItem(str(val or ""))
                item.setTextAlignment(Qt.AlignCenter)
                self.detail_table.setItem(r, c, item)

        counts = {}
        for rec in records:
            key = rec[1] or "（无车牌）"
            counts[key] = counts.get(key, 0) + 1
        self.counts = counts
        order = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        self.summary_table.setRowCount(len(order))
        for r, (plate, cnt) in enumerate(order):
            it0 = QTableWidgetItem(plate)
            it0.setTextAlignment(Qt.AlignCenter)
            it1 = QTableWidgetItem(str(cnt))
            it1.setTextAlignment(Qt.AlignCenter)
            self.summary_table.setItem(r, 0, it0)
            self.summary_table.setItem(r, 1, it1)
        self.result_label.setText(
            f"{start.isoformat()} 至 {end.isoformat()}：共 {len(records)} 条运货记录，{len(order)} 个车牌。")

    def export_detail(self):
        if not getattr(self, "records", None):
            QMessageBox.information(self, "提示", "请先查询。")
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出明细CSV", "运货明细.csv", "CSV文件 (*.csv)")
        if not path:
            return
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            wcsv = csv.writer(f)
            wcsv.writerow(DETAIL_HEADER)
            for rec in self.records:
                wcsv.writerow(rec)
        QMessageBox.information(self, "完成", "已导出：" + path)

    def export_summary(self):
        if not getattr(self, "counts", None):
            QMessageBox.information(self, "提示", "请先查询。")
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出汇总CSV", "运货汇总.csv", "CSV文件 (*.csv)")
        if not path:
            return
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            wcsv = csv.writer(f)
            wcsv.writerow(SUMMARY_HEADER)
            for plate, cnt in sorted(self.counts.items(), key=lambda kv: (-kv[1], kv[0])):
                wcsv.writerow([plate, cnt])
        QMessageBox.information(self, "完成", "已导出：" + path)


def _log_exception(exc_type, exc_value, tb):
    msg = "".join(traceback.format_exception(exc_type, exc_value, tb))
    try:
        log_path = os.path.join(_app_dir(), "运行错误日志.txt")
        with open(log_path, "a", encoding="utf-8") as f:
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
    w = StatsWindow()
    w.show()
    os._exit(app.exec())


if __name__ == "__main__":
    main()
