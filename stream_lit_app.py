import streamlit as st
import pandas as pd
import numpy as np
import random

@st.cache_data
def load_data():
    cards = pd.read_excel("processed_terms.xlsx")
    cosine_scores = np.load('data/cosine_scores.npy')
    return cards, cosine_scores

cards, cosine_scores = load_data()

# セッション状態の初期化
if 'probabilities' not in st.session_state:
    st.session_state.probabilities = {term: 1.0 for term in cards['term'].unique()}
if 'current_card' not in st.session_state:
    st.session_state.current_card = None
if 'current_definition' not in st.session_state:
    st.session_state.current_definition = None
if 'current_usage' not in st.session_state:
    st.session_state.current_usage = None
if 'last_term' not in st.session_state:
    st.session_state.last_term = None
if 'last_definition' not in st.session_state:
    st.session_state.last_definition = None
if 'last_usage' not in st.session_state:
    st.session_state.last_usage = None
if 'last_result' not in st.session_state:
    st.session_state.last_result = None
if 'button_clicked' not in st.session_state:
    st.session_state.button_clicked = False

st.title('暗記カードアプリ')

# カードをランダムに選択する関数
def pick_card():
    terms_list = list(st.session_state.probabilities.keys())
    probabilities_list = list(st.session_state.probabilities.values())
    return random.choices(terms_list, weights=probabilities_list, k=1)[0]

# コサイン類似度を利用して似た単語を取得する関数
def get_similar_definitions(term, lower_threshold=0.5, upper_threshold=0.8):
    term_indices = cards[cards['term'] == term].index.tolist()
    
    if not term_indices:
        return []
    
    valid_entries = []
    for idx in range(len(cards)):
        if cards['term'].iloc[idx] != term:
            max_similarity = max(cosine_scores[idx][term_indices])
            if lower_threshold <= max_similarity <= upper_threshold:
                valid_entries.append(cards['term'].iloc[idx])
    
    return random.sample(valid_entries, min(4, len(valid_entries)))

def update_card():
    st.session_state.current_card = pick_card()
    row = cards[cards['term'] == st.session_state.current_card].sample(1)
    st.session_state.current_definition = row["definition"].values[0]
    st.session_state.current_usage = row["usage"].values[0]

def button_callback(selected_term):
    st.session_state.last_term = st.session_state.current_card
    st.session_state.last_definition = st.session_state.current_definition
    st.session_state.last_usage = st.session_state.current_usage
    if selected_term == st.session_state.current_card:
        st.session_state.last_result = "正解！"
        st.session_state.probabilities[st.session_state.current_card] = max(st.session_state.probabilities[st.session_state.current_card] * 0.5, 0.1)
    else:
        st.session_state.last_result = "不正解！"
        st.session_state.probabilities[st.session_state.current_card] = min(st.session_state.probabilities[st.session_state.current_card] * 2, 10.0)
    
    update_card()
    st.session_state.button_clicked = True

# 初回実行時またはボタンクリック後に新しいカードを選択
if st.session_state.current_card is None or st.session_state.button_clicked:
    update_card()
    st.session_state.button_clicked = False

# 現在の定義を表示
st.markdown(f'<p style="font-size: 20px;"> {st.session_state.current_definition}</p>', unsafe_allow_html=True)

# 選択肢を作成
similar_terms = get_similar_definitions(st.session_state.current_card)
options = similar_terms + [st.session_state.current_card]
random.shuffle(options)

cols = st.columns(len(options))
for i, option in enumerate(options):
    cols[i].button(option, key=f'option_{i}', on_click=button_callback, args=(option,))

# 前回の単語と定義を表示
if st.session_state.last_term and st.session_state.last_definition:
    st.markdown(f'<p style="color: {"green" if st.session_state.last_result == "正解！" else "red"}; font-size: 16px;">結果: {st.session_state.last_result}</p>', unsafe_allow_html=True)
    st.markdown(f'<p style="color: blue; font-size: 16px;">前回の問題: {st.session_state.last_definition}</p>', unsafe_allow_html=True)
    st.markdown(f'<p style="color: green; font-size: 16px;">前回の答え: <b>{st.session_state.last_term}</b></p>', unsafe_allow_html=True)
    st.markdown(f'<p style="font-size: 14px;">使用例: {str(st.session_state.last_usage).replace("\n", "<br>")}</p>', unsafe_allow_html=True)