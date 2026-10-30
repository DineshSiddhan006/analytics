"""Power BI-inspired, static PNG pages for approved business analytics."""
from __future__ import annotations

from io import BytesIO
import math
from pathlib import Path
import re
import textwrap

import matplotlib
from matplotlib import font_manager
from matplotlib.colors import to_hex, to_rgb
from matplotlib.font_manager import FontProperties
from matplotlib.ticker import FuncFormatter

matplotlib.use('Agg')

from matplotlib.figure import Figure
from matplotlib.patches import FancyBboxPatch
import numpy as np
import pandas as pd

_BACKGROUND = '#F7F8FA'
_CARD = '#FFFFFF'
_TEXT = '#344054'
_MUTED = '#667085'
_BORDER = '#EAECF0'
_GRID = _BORDER
_BLUE = '#4386C6'
_ORANGE = '#F48E3A'
_GREEN = '#329D8F'
_BRIGHT_BLUE = '#65B6FB'
_CYAN = '#49D8F1'
_TEAL = '#26DAB9'
_PINK = '#F8829E'
_YELLOW = '#FFB000'
_DONUT_COLORS = (_CYAN, _TEAL, _PINK)
_FONT_DIR = Path(__file__).resolve().parents[1] / 'static' / 'fonts'
_FONT_FILES = (
    _FONT_DIR / 'Outfit-Regular.ttf',
    _FONT_DIR / 'Outfit-Medium.ttf',
    _FONT_DIR / 'Outfit-SemiBold.ttf',
)
for _font_file in _FONT_FILES:
    if not _font_file.is_file():
        raise FileNotFoundError(f'Required Outfit font file is missing: {_font_file}')
    font_manager.fontManager.addfont(str(_font_file))
for _font_weight in ('regular', 'medium', 'semibold'):
    font_manager.findfont(
        FontProperties(family='Outfit', weight=_font_weight),
        fallback_to_default=False,
    )
matplotlib.rcParams['font.family'] = 'Outfit'
matplotlib.rcParams['font.sans-serif'] = ['Outfit']


def _format_number(value):
    value = float(value)
    absolute = abs(value)
    if absolute >= 1_000_000:
        return f'{value / 1_000_000:.1f}M'.replace('.0M', 'M')
    if absolute >= 1_000:
        return f'{value / 1_000:.1f}k'.replace('.0k', 'k')
    return f'{value:,.0f}' if value.is_integer() else f'{value:g}'


def _format_bin_start(value):
    matches = re.findall(r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?', str(value))
    return _format_number(float(matches[0])) if matches else str(value)


def _segment_colors(count):
    colors = []
    for index in range(count):
        color = np.asarray(to_rgb(_DONUT_COLORS[index % len(_DONUT_COLORS)]))
        shade = index // len(_DONUT_COLORS)
        if shade:
            color += (1 - color) * min(0.28 * shade, 0.56)
        colors.append(to_hex(color).upper())
    return colors


def _is_compact_chart(item):
    spec, data = item['spec'], item['data']
    if data.empty:
        return True
    chart = spec.get('chart', 'bar')
    category_count = len(data)
    if chart in {'line', 'area'}:
        return category_count <= 12
    if chart in {'pie', 'donut', 'bar'}:
        return category_count <= 5
    return False


def _needs_full_width_chart(item):
    """True when the chart needs the full page width to stay readable."""
    spec, data = item['spec'], item['data']
    if data.empty:
        return False
    chart = spec.get('chart', 'bar')
    group = spec.get('group_by')
    cats = [
        _format_category(v, group)
        for v in data['category'].tolist()[:10]
    ]
    if not cats:
        return False
    max_len = max(len(str(c)) for c in cats)
    # Horizontal-bar charts: full-width when category names are long.
    if chart == 'barh':
        return max_len > 24
    # Vertical-bar charts: full-width when category names are long (e.g. routes/stations)
    # or when there are many categories with long labels.
    if chart == 'bar':
        n = min(len(cats), 10)
        return (n >= 7 and max_len >= 10) or max_len > 20
    return False


def _xaxis_label_rotation(categories):
    """Return 90 when vertical labels are needed on the x-axis, else 0."""
    if not categories:
        return 0
    n = len(categories)
    if n <= 1:
        return 0
    max_len = max(len(str(c)) for c in categories)
    # Short categories (months, quarters, day-of-week abbreviations, years) fit horizontally.
    if max_len <= 4:
        return 0
    # Few categories with moderately short text (e.g. Weekday/Weekend, North/South) fit horizontally.
    if n <= 3 and max_len <= 10:
        return 0
    # Otherwise (e.g. routes 'RUH / GEN (IMPORT)', stations, products, or many categories):
    # rotate vertically at 90 degrees to guarantee zero overlapping.
    return 90


_bar_label_rotation = _xaxis_label_rotation


def _extra_row_height_for_labels(row, base_height=4.2):
    """Return additional inches a row needs for vertical x-axis labels."""
    extra = 0.0
    for item in row:
        spec, data = item['spec'], item['data']
        if data.empty or spec.get('chart', 'bar') in {'pie', 'donut', 'barh'}:
            continue
        group = spec.get('group_by')
        cats = [
            _format_category(v, group)
            for v in data['category'].tolist()[:10]
        ]
        if not cats:
            continue
        rot = _xaxis_label_rotation(cats)
        if rot >= 90:
            max_len = max(len(str(c)) for c in cats)
            needed_in = (max_len * 0.09) + 0.35
            extra = max(extra, max(0.0, needed_in - 0.50))
    return extra


def _dashboard_rows(page):
    rows = []
    index = 0
    while index < len(page):
        if _needs_full_width_chart(page[index]):
            rows.append([page[index]])
            index += 1
            continue
        if _is_compact_chart(page[index]):
            end = index
            while (
                end < len(page)
                and end - index < 3
                and _is_compact_chart(page[end])
                and not _needs_full_width_chart(page[end])
            ):
                end += 1
            if (
                end - index == 1
                and end < len(page)
                and not _needs_full_width_chart(page[end])
            ):
                end += 1
            rows.append(page[index:end])
            index = end
        else:
            end = index + 1
            if end < len(page) and not _needs_full_width_chart(page[end]):
                end += 1
            rows.append(page[index:end])
            index = end
    return rows


_MONTH_ORDER = {
    month: index for index, names in enumerate((
        ('jan', 'january'), ('feb', 'february'), ('mar', 'march'),
        ('apr', 'april'), ('may',), ('jun', 'june'), ('jul', 'july'),
        ('aug', 'august'), ('sep', 'september'), ('oct', 'october'),
        ('nov', 'november'), ('dec', 'december'),
    ), start=1) for month in names
}
def _format_category(value, group):
    text = str(value)
    name = str(group or '').lower()
    if name == 'month':
        try:
            month = int(float(text))
        except ValueError:
            return text
        if 1 <= month <= 12:
            return pd.Timestamp(month=month, year=2000, day=1).strftime('%b')
    if name == 'quarter':
        try:
            quarter = int(float(text))
        except ValueError:
            return text
        if 1 <= quarter <= 4:
            return f'Q{quarter}'
    if name in {'day_of_week', 'weekday'}:
        try:
            day = int(float(text))
        except ValueError:
            return text
        if 1 <= day <= 7:
            return ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')[day - 1]
    return text


def _is_time_axis(categories, spec):
    if spec.get('period'):
        return True
    group = str(spec.get('group_by') or '').lower()
    if group in {'month', 'quarter', 'year'}:
        return True
    if any(token in group for token in ('date', 'time', 'timestamp')):
        return True
    if categories and all(str(value).strip().lower() in _MONTH_ORDER for value in categories):
        return True
    return bool(categories) and all(
        re.fullmatch(r'\d{4}[-/]\d{1,2}(?:[-/]\d{1,2})?', str(value))
        for value in categories
    )


def _draw_chart(axis, item, card_height_in=4.2):
    spec, data = item['spec'], item['data']
    title = spec.get('title') or spec.get('business_question') or 'Business analysis'
    chart = spec.get('chart', 'bar')
    axis.patch = FancyBboxPatch(
        (0, 0),
        1,
        1,
        boxstyle='round,pad=0.012,rounding_size=0.03',
        transform=axis.transAxes,
        facecolor=_CARD,
        edgecolor=_BORDER,
        linewidth=1,
        zorder=-1,
    )
    axis.set_xticks([])
    axis.set_yticks([])
    axis.grid(False)
    for spine in axis.spines.values():
        spine.set_visible(False)
    axis.text(
        0.035,
        0.96,
        textwrap.fill(str(title), width=42),
        transform=axis.transAxes,
        color=_TEXT,
        fontsize=16,
        fontweight='semibold',
        va='top',
        ha='left',
        linespacing=1.15,
    )
    wide_chart = _needs_full_width_chart(item)

    # Calculate dynamic bottom margin for charts with x-axis labels
    _bottom_margin = 0.12
    if chart not in {'pie', 'donut', 'barh'} and not data.empty:
        _group = spec.get('group_by')
        _preview = [
            _format_category(v, _group)
            for v in data['category'].tolist()[:10]
        ]
        _rot = _xaxis_label_rotation(_preview)
        if _rot >= 90:
            _max_len = max(len(str(c)) for c in _preview)
            _needed_in = (_max_len * 0.09) + 0.35
            _bottom_margin = min(0.60, max(0.12, _needed_in / card_height_in))

    if chart == 'barh':
        chart_position = [0.25, 0.12, 0.72, 0.76] if wide_chart else [0.37, 0.12, 0.60, 0.76]
    else:
        _chart_top = min(0.92, max(0.80, 1.0 - (0.50 / card_height_in)))
        _chart_height = max(0.35, _chart_top - _bottom_margin)
        chart_position = [0.10, _bottom_margin, 0.87, _chart_height]

    chart_axis = axis.inset_axes(chart_position)
    chart_axis.set_facecolor('none')
    chart_axis.tick_params(colors=_MUTED, labelsize=12, length=0)
    for spine in chart_axis.spines.values():
        spine.set_visible(False)
    chart_axis.grid(axis='y', color=_GRID, linewidth=0.7)
    chart_axis.set_axisbelow(True)

    if data.empty:
        chart_axis.set_axis_off()
        return chart_axis

    group = spec.get('group_by')
    raw_categories = data['category'].tolist()
    categories = [_format_category(value, group) for value in raw_categories]
    values = np.nan_to_num(data['value'].to_numpy(dtype=float), nan=0.0)
    is_time = _is_time_axis(categories, spec)
    if str(group).lower() in {'day_of_week', 'weekday'}:
        try:
            numeric_days = {int(float(value)) for value in raw_categories}
        except (TypeError, ValueError):
            numeric_days = set()
        if 0 in numeric_days:
            categories = [
                ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')[int(float(value))]
                if str(value).replace('.0', '').isdigit() and 0 <= int(float(value)) <= 6
                else category
                for value, category in zip(raw_categories, categories)
            ]
    if chart in {'pie', 'donut'}:
        chart_axis.grid(False)
        chart_axis.set_axis_off()
        pie_axis = chart_axis.inset_axes([0.01, 0.04, 0.58, 0.92])
        pie_axis.set_facecolor('none')
        wedges, _, _ = pie_axis.pie(
            values,
            labels=None,
            colors=_segment_colors(len(values)),
            autopct='%1.0f%%',
            pctdistance=0.78 if chart == 'donut' else 0.65,
            textprops={'color': _TEXT, 'fontsize': 11},
            wedgeprops={'width': 0.4, 'edgecolor': _CARD} if chart == 'donut' else {'edgecolor': _CARD},
            startangle=90,
        )
        pie_axis.set_axis_off()
        chart_axis.legend(
            wedges,
            [textwrap.fill(value, width=16) for value in categories],
            loc='center left',
            bbox_to_anchor=(0.63, 0.5),
            frameon=False,
            fontsize=10,
            labelcolor=_TEXT,
        )
        return chart_axis

    if chart in {'line', 'area'} and is_time and len(categories) > 1:
        if group in {'month', 'quarter', 'year'}:
            try:
                order = np.argsort([float(value) for value in data['category']])
            except (TypeError, ValueError):
                order = np.arange(len(categories))
        else:
            try:
                order = np.argsort(pd.to_datetime(data['category'], errors='raise').to_numpy())
            except (ValueError, TypeError):
                order = np.arange(len(categories))
        categories = [categories[index] for index in order]
        values = values[order]
        positions = np.arange(len(categories))
        chart_axis.plot(positions, values, color=_BLUE, marker='o', linewidth=2.5, markersize=4)
        if chart == 'area':
            chart_axis.fill_between(positions, values, color=_BLUE, alpha=0.12)
        tick_step = max(1, int(math.ceil(len(categories) / 8)))
        ticks = positions[::tick_step]
        tick_labels = [categories[index] for index in ticks]
        chart_axis.set_xticks(ticks, labels=tick_labels)
        rot = _xaxis_label_rotation(tick_labels)
        if rot >= 90:
            chart_axis.tick_params(axis='x', rotation=90)
            for tick in chart_axis.get_xticklabels():
                tick.set_ha('center')
                tick.set_va('top')
        else:
            chart_axis.tick_params(axis='x', labelrotation=0)
        chart_axis.grid(axis='y', color=_GRID, linewidth=0.7)
        _set_nonnegative_baseline(chart_axis, values, 'y')
    elif chart == 'histogram':
        positions = np.arange(len(categories))
        chart_axis.bar(positions, values, color=_BLUE, width=0.82)
        tick_step = max(1, int(math.ceil(len(categories) / 6)))
        ticks = positions[::tick_step]
        bin_labels = [_format_bin_start(categories[index]) for index in ticks]
        chart_axis.set_xticks(ticks, labels=bin_labels)
        rot = _xaxis_label_rotation(bin_labels)
        if rot >= 90:
            chart_axis.tick_params(axis='x', rotation=90)
            for tick in chart_axis.get_xticklabels():
                tick.set_ha('center')
                tick.set_va('top')
        else:
            chart_axis.tick_params(axis='x', rotation=0)
        chart_axis.set_xlabel(str(spec.get('metric', '')).replace('_', ' '), color=_MUTED, fontsize=12)
        chart_axis.set_ylabel('Shipments', color=_MUTED, fontsize=12)
        chart_axis.yaxis.set_major_formatter(FuncFormatter(lambda value, _: _format_number(value)))
        _set_nonnegative_baseline(chart_axis, values, 'y')
    elif chart == 'barh':
        # A compact, single-color ranking keeps category names legible.
        if len(categories) > 10:
            categories, values = categories[:10], values[:10]
        positions = np.arange(len(categories))
        label_width = 38 if wide_chart else 26
        labels = [textwrap.fill(value, width=label_width) for value in categories]
        bars = chart_axis.barh(positions, values, color=_BLUE, height=0.68)
        chart_axis.set_yticks(positions, labels=labels)
        chart_axis.invert_yaxis()
        chart_axis.grid(False)
        chart_axis.tick_params(axis='y', labelsize=12)
        chart_axis.xaxis.set_major_formatter(FuncFormatter(lambda value, _: _format_number(value)))
        chart_axis.bar_label(bars, labels=[_format_number(value) for value in values], padding=4, fontsize=11, color=_TEXT)
        _set_nonnegative_baseline(chart_axis, values, 'x')
    else:
        if len(categories) > 10:
            categories, values = categories[:10], values[:10]
        positions = np.arange(len(categories))
        bars = chart_axis.bar(positions, values, color=_BLUE, width=0.72)
        rotation = _xaxis_label_rotation(categories)
        if rotation >= 90:
            chart_axis.set_xticks(positions, labels=list(categories))
            chart_axis.tick_params(axis='x', rotation=90)
            for tick in chart_axis.get_xticklabels():
                tick.set_ha('center')
                tick.set_va('top')
        else:
            labels = [textwrap.fill(str(c), width=14) for c in categories]
            chart_axis.set_xticks(positions, labels=labels, rotation=0, ha='center')
        chart_axis.bar_label(bars, labels=[_format_number(value) for value in values], padding=3, fontsize=11, color=_TEXT)
        _set_nonnegative_baseline(chart_axis, values, 'y')

    chart_axis.tick_params(axis='x', colors=_MUTED, labelsize=12)
    chart_axis.tick_params(axis='y', colors=_MUTED, labelsize=12)
    if chart != 'barh':
        chart_axis.yaxis.set_major_formatter(FuncFormatter(lambda value, _: _format_number(value)))
    chart_axis.margins(x=0.02, y=0.02)
    return chart_axis


def _set_nonnegative_baseline(axis, values, dimension):
    if not len(values) or np.any(values < 0):
        return
    maximum = float(np.max(values))
    upper = maximum * 1.16 if maximum > 0 else 1.0
    if dimension == 'x':
        axis.set_xlim(left=0, right=upper)
    else:
        axis.set_ylim(bottom=0, top=upper)


def make_dashboard_pngs(outputs, charts_per_page=6) -> list[bytes]:
    """Render up to six chart cards per page, sizing rows for chart density."""
    if not 1 <= charts_per_page <= 6:
        raise ValueError('charts_per_page must be between 1 and 6.')
    images = []
    for start in range(0, len(outputs), charts_per_page):
        page = outputs[start:start + charts_per_page]
        rows = _dashboard_rows(page)
        row_heights = []
        for row in rows:
            # Base height: taller for dense horizontal-bar rows.
            if any(_needs_full_width_chart(item) for item in row
                   if item['spec'].get('chart') == 'barh'):
                base_h = max(4.2, 0.5 * max(len(item['data']) for item in row) + 0.2)
            else:
                base_h = 4.2
            # Extra height for rows that need vertical x-axis labels.
            extra_h = _extra_row_height_for_labels(row, base_height=base_h)
            row_heights.append(base_h + extra_h)
        figure_height = max(7.5, 1.4 + sum(row_heights))
        figure = Figure(figsize=(16, figure_height), facecolor=_BACKGROUND)
        figure.suptitle(
            'Cargo Tonnage Prediction',
            color=_TEXT,
            fontsize=24,
            fontweight='semibold',
            x=0.02,
            ha='left',
            y=0.94,
        )
        layout = figure.add_gridspec(
            len(rows),
            1,
            height_ratios=row_heights,
            left=0.018,
            right=0.982,
            top=0.86,
            bottom=0.08,
            hspace=0.22,
        )
        for row_index, row in enumerate(rows):
            columns = len(row)
            row_layout = layout[row_index].subgridspec(
                1,
                columns,
                wspace=0.06,
            )
            card_h = row_heights[row_index]
            axes = [figure.add_subplot(row_layout[0, index]) for index in range(columns)]
            for axis, item in zip(axes, row):
                _draw_chart(axis, item, card_height_in=card_h)
        image = BytesIO()
        figure.savefig(image, format='png', dpi=120, facecolor=_BACKGROUND)
        images.append(image.getvalue())
    return images
