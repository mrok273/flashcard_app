import streamlit as st
import pandas as pd
import numpy as np
import random
import sqlite3
from datetime import datetime
import time


# データベース接続をグローバルに保持
@st.cache_resource
def get_db_connection():
    return sqlite3.connect('flashcards.db', check_same_thread=False)

@st.cache_data
def load_data():
    cards = pd.read_excel("processed_terms.xlsx")
    cosine_scores = np.load('data/cosine_scores.npy')
    return cards, cosine_scores

def init_db():
    conn = sqlite3.connect('flashcards.db')
    c = conn.cursor()
    #存在しないときだけ作成
    c.execute('''CREATE TABLE IF NOT EXISTS attempts
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp TEXT,
                  question TEXT,
                  correct_answer TEXT,
                  user_answer TEXT,
                  other_options TEXT,
                  is_correct INTEGER,
                  time_taken REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS probabilities
                 (term TEXT PRIMARY KEY,
                  probability REAL)''')
    conn.commit()
    conn.close()
    
#一度だけ関数を定義するためのデコレータ
def singleton_function(func):
    def wrapper(*args, **kwargs):
        if not wrapper.has_run:
            wrapper.has_run = True
            return func(*args, **kwargs)
    wrapper.has_run = False
    return wrapper
    
@singleton_function
def save_probability():
    def update_probability(term, probability):
        conn = sqlite3.connect('flashcards.db')
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO probabilities (term, probability)
                     VALUES (?, ?)''', (term, probability))
        conn.commit()
        conn.close()
    return update_probability

# 初回のみ作成される update_probability 関数
update_probability = save_probability()

def update_probability(term, probability):
    conn = sqlite3.connect('flashcards.db')
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO probabilities (term, probability)
                 VALUES (?, ?)''', (term, probability))
    conn.commit()
    conn.close()

def load_probabilities():
    conn = sqlite3.connect('flashcards.db')
    c = conn.cursor()
    c.execute('SELECT term, probability FROM probabilities')
    loaded_probs = dict(c.fetchall())
    conn.close()
    
    # デフォルト値（1.0）で初期化
    default_probs = {term: 1.0 for term in cards['term'].unique()}
    
    # ロードした値で更新
    default_probs.update(loaded_probs)
    
    return default_probs

# カードをランダムに選択する関数
def pick_card():
    terms_list = list(st.session_state.probabilities.keys())
    probabilities_list = list(st.session_state.probabilities.values())
    return random.choices(terms_list, weights=probabilities_list, k=1)[0]




# アプリの起動時にデータベースを初期化
init_db()

cards, cosine_scores = load_data()

# セッション状態の初期化
if 'probabilities' not in st.session_state:
    st.session_state.probabilities = load_probabilities()

# セッション状態の初期化
if 'start_time' not in st.session_state:
    st.session_state.start_time = time.time()
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
    end_time = time.time()
    time_taken = end_time - st.session_state.start_time
    st.session_state.last_term = st.session_state.current_card
    st.session_state.last_definition = st.session_state.current_definition
    st.session_state.last_usage = st.session_state.current_usage
    
    is_correct = selected_term == st.session_state.current_card
    if is_correct:
        st.session_state.last_result = "正解！"
        st.session_state.probabilities[st.session_state.current_card] = max(st.session_state.probabilities[st.session_state.current_card] * 0.5, 0.1)
    else:
        st.session_state.last_result = "不正解！"
        st.session_state.probabilities[st.session_state.current_card] = min(st.session_state.probabilities[st.session_state.current_card] * 2, 10.0)
        
    # 更新された確率をデータベースに保存
    update_probability(st.session_state.current_card, st.session_state.probabilities[st.session_state.current_card])        

    # データベースに結果を保存
    conn = sqlite3.connect('flashcards.db')
    c = conn.cursor()
    c.execute('''INSERT INTO attempts (timestamp, question, correct_answer, user_answer, other_options, is_correct, time_taken)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
              (datetime.now().isoformat(), st.session_state.current_definition, st.session_state.current_card,
               selected_term, ','.join(options), int(is_correct), time_taken))
    conn.commit()
    conn.close()        
    
    update_card()
    st.session_state.button_clicked = True
    st.session_state.start_time = time.time()  # 次の問題の開始時間をリセット

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
    
    
def show_history():
    conn = sqlite3.connect('flashcards.db')
    df = pd.read_sql_query("SELECT * FROM attempts ORDER BY timestamp DESC LIMIT 10", conn)
    conn.close()
    st.dataframe(df)

# アプリの最後に履歴表示ボタンを追加
if st.button("学習履歴を表示"):
    show_history()