from io import BytesIO

import pandas as pd
from PIL import Image

from bi_pipeline.charts import make_dashboard_pngs
from bi_pipeline.results import build_results


def test_dashboard_is_rendered_as_a_static_png():
    df = pd.DataFrame({
        'Route': ['North', 'South', 'North'],
        'Tonnage': [10, 20, 15],
    })
    specs = [{
        'title': 'Cargo tonnage by route',
        'business_question': 'Which routes carry the most tonnage?',
        'metric': 'Tonnage',
        'aggregation': 'sum',
        'group_by': 'Route',
        'chart': 'barh',
        'period': None,
        'filters': [],
    }]
    outputs = build_results(df, specs)

    images = make_dashboard_pngs(outputs)
    image = images[0]
    rendered = Image.open(BytesIO(image)).convert('RGB')
    width, height = rendered.size

    assert image.startswith(b'\x89PNG\r\n\x1a\n')
    assert len(image) > 1000
    assert 1.6 < width / height < 2.3
    assert rendered.getpixel((0, 0)) == (247, 248, 250)
    card_sample = rendered.crop((0, 100, width, height - 100))
    colors = card_sample.getcolors(maxcolors=card_sample.width * card_sample.height)
    assert colors is not None and (255, 255, 255) in {color for _, color in colors}
    assert len(images) == 1
    assert 'figure' not in outputs[0]


def test_large_categorical_chart_is_rendered_as_readable_png():
    df = pd.DataFrame({
        'Route': [f'Route {index}' for index in range(40)],
        'Tonnage': list(range(1, 41)),
    })
    output = build_results(df, [{
        'title': 'Cargo tonnage by route',
        'metric': 'Tonnage',
        'aggregation': 'sum',
        'group_by': 'Route',
        'chart': 'bar',
        'period': None,
        'filters': [],
    }])[0]

    image = make_dashboard_pngs([output])[0]

    assert image.startswith(b'\x89PNG\r\n\x1a\n')


def test_dashboard_splits_many_visuals_into_readable_pages():
    outputs = [{
        'spec': {'title': f'Analysis {index}', 'chart': 'bar', 'group_by': 'Region'},
        'data': pd.DataFrame({'category': ['North', 'South'], 'value': [index + 2, 1]}),
    } for index in range(7)]

    images = make_dashboard_pngs(outputs)

    assert len(images) == 2
    assert all(image.startswith(b'\x89PNG\r\n\x1a\n') for image in images)


def test_review_and_dashboard_do_not_render_raw_diagnostics_or_interactive_charts():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    app = (root / 'app.py').read_text(encoding='utf-8')
    dashboard = (root / 'ui' / 'dashboard.py').read_text(encoding='utf-8')

    assert "run['profile']['rows']" not in app
    assert 'st.json(run[' not in app
    assert 'render_assistant' not in app
    assert 'plotly_chart' not in dashboard
    assert 'st.dataframe' not in dashboard
    assert 'make_dashboard_pngs(bundle[\'outputs\'])' in dashboard


def test_dashboard_uses_the_light_style_guide_palette_and_typography():
    from pathlib import Path

    from ui.styles import CSS
    from bi_pipeline.charts import _DONUT_COLORS, _FONT_FILES, _segment_colors, matplotlib

    root = Path(__file__).resolve().parents[1]
    assert '#F7F8FA' in CSS
    assert '#FFFFFF' in CSS
    assert '#344054' in CSS
    assert '#667085' in CSS
    assert '#EAECF0' in CSS
    assert 'font-family: "Outfit"' in CSS
    assert all(font.is_file() for font in _FONT_FILES)
    assert matplotlib.rcParams['font.sans-serif'] == ['Outfit']
    assert _segment_colors(3) == list(_DONUT_COLORS)
    assert _segment_colors(4)[3] not in {'#FFB000', '#4386C6', '#F48E3A'}
    assert CSS.count('font-display: block') == 3
    assert all(font.name in CSS for font in _FONT_FILES)
    assert 'enableStaticServing = true' in (root / '.streamlit' / 'config.toml').read_text(encoding='utf-8')
    streamlit_config = (root / '.streamlit' / 'config.toml').read_text(encoding='utf-8')
    assert 'base = "light"' in streamlit_config
    assert 'backgroundColor = "#F7F8FA"' in streamlit_config
    assert '-webkit-text-fill-color: var(--text)' in CSS


def test_dashboard_renders_up_to_six_compact_charts_per_page():
    outputs = [{
        'spec': {'title': f'Analysis {index}', 'chart': 'bar', 'group_by': 'Region'},
        'data': pd.DataFrame({'category': ['North', 'South'], 'value': [index + 2, 1]}),
    } for index in range(6)]

    assert len(make_dashboard_pngs(outputs)) == 1


def test_dashboard_uses_three_columns_for_small_and_two_for_dense_charts():
    from bi_pipeline.charts import _dashboard_rows

    compact = {
        'spec': {'chart': 'bar'},
        'data': pd.DataFrame({'category': ['North', 'South'], 'value': [10, 5]}),
    }
    dense = {
        'spec': {'chart': 'histogram'},
        'data': pd.DataFrame({'category': [str(index) for index in range(12)], 'value': range(12)}),
    }
    assert [len(row) for row in _dashboard_rows([compact, compact, compact])] == [3]
    assert [len(row) for row in _dashboard_rows([dense, dense, compact])] == [2, 1]


def test_horizontal_bars_keep_category_labels_instead_of_numeric_indices():
    from bi_pipeline.charts import Figure, _draw_chart

    item = {
        'spec': {'title': 'Cargo by route', 'chart': 'barh', 'group_by': 'route'},
        'data': pd.DataFrame({
            'category': ['North route', 'South route'],
            'value': [25, 20],
        }),
    }
    figure = Figure(figsize=(8, 4))
    axis = figure.subplots()
    chart_axis = _draw_chart(axis, item)

    assert [tick.get_text() for tick in chart_axis.get_yticklabels()] == ['North route', 'South route']


def test_vertical_bar_axis_does_not_show_negative_values_for_nonnegative_data():
    from bi_pipeline.charts import Figure, _draw_chart

    item = {
        'spec': {'title': 'Cargo by route', 'chart': 'bar'},
        'data': pd.DataFrame({'category': ['North', 'South'], 'value': [25, 20]}),
    }
    figure = Figure(figsize=(8, 4))
    panel = figure.subplots()
    chart_axis = _draw_chart(panel, item)

    assert chart_axis.get_ylim()[0] == 0
    assert chart_axis.get_ylim()[1] > 25


def test_single_chart_uses_full_row_and_never_a_centered_blank_column():
    from bi_pipeline.charts import _dashboard_rows

    chart = {
        'spec': {'chart': 'bar'},
        'data': pd.DataFrame({'category': ['North', 'South'], 'value': [10, 5]}),
    }
    assert [len(row) for row in _dashboard_rows([chart])] == [1]
    image = make_dashboard_pngs([chart])[0]
    assert image.startswith(b'\x89PNG\r\n\x1a\n')


def test_long_route_labels_get_a_full_width_chart_row():
    from bi_pipeline.charts import _dashboard_rows

    compact = {
        'spec': {'chart': 'bar'},
        'data': pd.DataFrame({'category': ['North', 'South'], 'value': [10, 5]}),
    }
    wide = {
        'spec': {'chart': 'barh', 'group_by': 'route'},
        'data': pd.DataFrame({
            'category': [
                f'Riyadh (RUH) - General Cargo (GEN) (Transit {kind})'
                for kind in ('Outbound', 'Inbound', 'Export', 'Import', 'Outbound', 'Inbound', 'Export', 'Import')
            ],
            'value': [96, 88, 75, 61, 55, 43, 32, 22],
        }),
    }

    assert [len(row) for row in _dashboard_rows([compact, wide])] == [1, 1]
    assert make_dashboard_pngs([wide])[0].startswith(b'\x89PNG\r\n\x1a\n')


def test_single_period_does_not_render_as_a_floating_point():
    output = {
        'spec': {'title': 'Cargo weight by quarter', 'chart': 'line', 'group_by': 'quarter'},
        'data': pd.DataFrame({'category': ['Q1'], 'value': [20500]}),
    }
    image = make_dashboard_pngs([output])[0]
    assert image.startswith(b'\x89PNG\r\n\x1a\n')
