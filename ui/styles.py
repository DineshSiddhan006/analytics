CSS = '''<style>
:root {
    --page: #F7F8FA;
    --card: #FFFFFF;
    --text: #344054;
    --muted: #667085;
    --border: #EAECF0;
    --blue: #4386C6;
    --orange: #F48E3A;
    --green: #329D8F;
}
@font-face {
    font-family: "Outfit";
    src: url("/app/static/fonts/Outfit-Regular.ttf") format("truetype");
    font-style: normal;
    font-weight: 400;
    font-display: block;
}
@font-face {
    font-family: "Outfit";
    src: url("/app/static/fonts/Outfit-Medium.ttf") format("truetype");
    font-style: normal;
    font-weight: 500;
    font-display: block;
}
@font-face {
    font-family: "Outfit";
    src: url("/app/static/fonts/Outfit-SemiBold.ttf") format("truetype");
    font-style: normal;
    font-weight: 600;
    font-display: block;
}
html, body, [class*="css"] {
    font-family: "Outfit";
    color: var(--text);
}
.stApp { background: var(--page); }
.stApp h1, .stApp h2, .stApp h3,
.stApp [data-testid="stMarkdownContainer"] p,
.stApp label, .stApp [data-testid="stCaptionContainer"] {
    color: var(--text) !important;
    -webkit-text-fill-color: var(--text);
}
.stApp [data-testid="stCaptionContainer"] {
    color: var(--muted) !important;
    -webkit-text-fill-color: var(--muted);
}
.block-container {
    padding: 1rem 0 1.5rem !important;
    max-width: 100% !important;
}
h1, h2, h3 {
    color: var(--text) !important;
    -webkit-text-fill-color: var(--text);
    font-family: "Outfit";
    font-weight: 600;
    letter-spacing: -0.02em;
}
h1 { font-size: 1.75rem; line-height: 2rem; }
h2 { font-size: 1.25rem; line-height: 1.75rem; }
h3 { font-size: 1rem; line-height: 1.5rem; }
p, label {
    color: var(--text) !important;
}
[data-testid="stCaptionContainer"] {
    color: var(--muted) !important;
}
section[data-testid="stSidebar"] {
    background: var(--card);
    border-right: 1px solid var(--border);
}
div[data-testid="stImage"] {
    width: 100%;
    margin: 0;
    padding: 0;
}
div[data-testid="stImage"] img {
    display: block;
    width: 100%;
    height: auto;
}
div[data-testid="stButton"] > button,
div[data-testid="stFormSubmitButton"] > button {
    border-radius: 8px;
    font-family: "Outfit";
    font-weight: 500;
}
div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div,
div[data-baseweb="textarea"] > div {
    background: var(--card) !important;
    border-color: var(--border) !important;
}
div[data-baseweb="input"] input,
div[data-baseweb="select"] input,
div[data-baseweb="select"] div,
div[data-baseweb="textarea"] textarea {
    color: var(--text) !important;
    -webkit-text-fill-color: var(--text);
    font-family: "Outfit";
}
</style>'''
