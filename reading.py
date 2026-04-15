"""
reading.py — TEN IELTS Reading Mock Test
Streamlit + Supabase
"""
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
from utils import get_supabase

# ─────────────────────────────────────────
# КОНФИГ
# ─────────────────────────────────────────
READING_SECONDS = 60 * 60  # 60 минут

st.set_page_config(
    page_title="TEN: IELTS Reading",
    page_icon="📖",
    layout="wide",
)
st.markdown("""
<style>
  [data-testid="stSidebar"]{display:none;}
  [data-testid="collapsedControl"]{display:none;}
  .block-container{padding-top:1.5rem!important;}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────
# DB ФУНКЦИЯЛАРЫ
# ─────────────────────────────────────────

@st.cache_data(ttl=300)
def fetch_student_names() -> list[str]:
    try:
        res = get_supabase().table("students").select("name").order("name").execute()
        return [r["name"] for r in (res.data or [])]
    except Exception:
        return []


@st.cache_data(ttl=60)
def fetch_active_tests() -> list[dict]:
    """Белсенді Reading тесттерін тартады."""
    try:
        res = (get_supabase().table("tests")
               .select("*")
               .eq("type", "reading")
               .eq("is_active", True)
               .order("created_at", desc=True)
               .execute())
        return res.data or []
    except Exception:
        return []


def fetch_test_data(test_id: int) -> dict | None:
    """Тест + секциялар + сұрақтарды толық тартады."""
    try:
        sections_res = (get_supabase().table("test_sections")
                        .select("*")
                        .eq("test_id", test_id)
                        .order("order_num")
                        .execute())
        sections = sections_res.data or []

        for sec in sections:
            q_res = (get_supabase().table("questions")
                     .select("*")
                     .eq("section_id", sec["id"])
                     .order("order_num")
                     .execute())
            sec["questions"] = q_res.data or []

        return {"sections": sections}
    except Exception:
        return None


def fetch_attempt(test_id: int, student_name: str) -> dict | None:
    """Оқушының осы тест бойынша соңғы attempt-ін тартады."""
    try:
        res = (get_supabase().table("test_attempts")
               .select("*")
               .eq("test_id", test_id)
               .eq("student_name", student_name)
               .order("started_at", desc=True)
               .limit(1)
               .execute())
        return res.data[0] if res.data else None
    except Exception:
        return None


def create_attempt(test_id: int, student_name: str) -> int | None:
    """Жаңа attempt жасайды, ID қайтарады."""
    try:
        res = (get_supabase().table("test_attempts")
               .insert({
                   "test_id":      test_id,
                   "student_name": student_name,
                   "started_at":   datetime.now().isoformat(),
               })
               .execute())
        return res.data[0]["id"] if res.data else None
    except Exception:
        return None


def submit_attempt(attempt_id: int, answers: dict, score: int, band: float) -> bool:
    """Жауаптар мен нәтижені DB-ге жазады."""
    try:
        get_supabase().table("test_attempts").update({
            "answers_json": answers,
            "score":        score,
            "band":         band,
            "submitted_at": datetime.now().isoformat(),
        }).eq("id", attempt_id).execute()
        return True
    except Exception:
        return False


# ─────────────────────────────────────────
# BAND ЕСЕПТЕУ (IELTS Academic Reading)
# ─────────────────────────────────────────

BAND_TABLE = {
    40: 9.0, 39: 8.5, 38: 8.5, 37: 8.0, 36: 8.0,
    35: 7.5, 34: 7.0, 33: 6.5, 32: 6.5, 31: 6.0,
    30: 6.0, 29: 5.5, 28: 5.5, 27: 5.0, 26: 5.0,
    25: 5.0, 24: 4.5, 23: 4.5, 22: 4.0, 21: 4.0,
    20: 4.0, 19: 3.5, 18: 3.5, 17: 3.0, 16: 3.0,
}

def score_to_band(score: int) -> float:
    score = max(0, min(40, score))
    return BAND_TABLE.get(score, 2.5)


# ─────────────────────────────────────────
# ЖАУАПТЫ ТЕКСЕРУ
# ─────────────────────────────────────────

def check_answer(q: dict, user_ans: str) -> bool:
    correct = str(q.get("correct_answer", "")).strip().lower()
    user    = str(user_ans or "").strip().lower()
    if not user:
        return False
    # Fill-in: үтір арқылы бірнеше дұрыс жауап болуы мүмкін
    if q.get("question_type") in ("fill_blank", "short_answer"):
        alts = [a.strip() for a in correct.split("|")]
        return user in alts
    return user == correct


# ─────────────────────────────────────────
# НӘТИЖЕ БЕТІ
# ─────────────────────────────────────────

def show_result(score: int, total: int, band: float,
                questions: list, answers: dict):
    st.success("✅ Тест сәтті тапсырылды!")
    st.markdown(
        f"<h2 style='text-align:center;color:#1E88E5;'>"
        f"🏆 Band Score: {band}</h2>",
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns(2)
    c1.metric("Дұрыс жауап", f"{score} / {total}")
    c2.metric("Band", band)

    st.markdown("---")
    st.subheader("📋 Жауаптар талдауы")

    q_num = 1
    for q in questions:
        user_ans = answers.get(str(q["id"]), "")
        correct  = check_answer(q, user_ans)
        icon     = "✅" if correct else "❌"
        qtype    = q.get("question_type", "")

        with st.expander(f"{icon} Сұрақ {q_num}: {q['question_text'][:80]}..."):
            st.markdown(f"**Сіздің жауабыңыз:** `{user_ans or '—'}`")
            st.markdown(f"**Дұрыс жауап:** `{q['correct_answer']}`")
            if qtype in ("mcq",) and q.get("options_json"):
                st.caption("Нұсқалар: " + " | ".join(q["options_json"]))
        q_num += 1


# ─────────────────────────────────────────
# READING HTML КОМПОНЕНТІ (таймер + античит)
# ─────────────────────────────────────────

def build_reading_timer_html(session_id: str, total_seconds: int,
                              sb_url: str, sb_key: str) -> str:
    """Тек таймер + античит логикасы бар HTML iframe."""
    return f"""
<style>
*{{box-sizing:border-box;margin:0;padding:0;font-family:sans-serif;}}
body{{background:transparent;padding:4px 0;}}
#timer-wrap{{display:flex;align-items:center;gap:10px;}}
#timer-box{{
  background:#EAF3DE;border:1.5px solid #639922;
  border-radius:12px;padding:6px 16px;text-align:center;min-width:90px;
  transition:background .5s,border-color .5s;
}}
#timer-label{{font-size:10px;color:#3B6D11;text-transform:uppercase;margin-bottom:1px;}}
#timer-display{{font-size:22px;font-weight:600;color:#27500A;letter-spacing:1px;}}
#timer-box.yellow{{background:#FAEEDA;border-color:#EF9F27;}}
#timer-box.yellow #timer-label{{color:#854F0B;}}
#timer-box.yellow #timer-display{{color:#633806;}}
#timer-box.red{{background:#FCEBEB;border-color:#E24B4A;}}
#timer-box.red #timer-label{{color:#A32D2D;}}
#timer-box.red #timer-display{{color:#501313;}}
#timer-box.done{{background:#F09595;border-color:#E24B4A;animation:pulse 1s ease-in-out infinite;}}
@keyframes pulse{{0%,100%{{transform:scale(1);}}50%{{transform:scale(1.04);}}}}
#status-bar{{
  flex:1;padding:8px 14px;border-radius:8px;
  background:#EAF3DE;border-left:4px solid #639922;
  font-size:13px;color:#3B6D11;
}}
</style>

<div id="timer-wrap">
  <div id="timer-box">
    <div id="timer-label">Уақыт</div>
    <div id="timer-display">60:00</div>
  </div>
  <div id="status-bar" id="sb">📖 Тест басталды. Сәттілік!</div>
</div>

<script>
(function(){{
  const TOTAL = {total_seconds};
  const SESSION = "{session_id}";
  const LS_KEY  = "reading_start_" + SESSION;
  const SB_URL  = "{sb_url}";
  const SB_KEY  = "{sb_key}";
  const H = {{
    "apikey": SB_KEY,
    "Authorization": "Bearer " + SB_KEY,
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates",
  }};

  const tBox  = document.getElementById('timer-box');
  const tDisp = document.getElementById('timer-display');
  const sb    = document.getElementById('status-bar');

  let blurCnt = 0;
  let timerID = null;

  function fmt(s) {{
    const m = Math.floor(s/60), sec = s%60;
    return String(m).padStart(2,'0')+':'+String(sec).padStart(2,'0');
  }}

  function setBar(msg, bg, border, color) {{
    sb.textContent = msg;
    sb.style.background = bg;
    sb.style.borderLeftColor = border;
    sb.style.color = color;
  }}

  // Таймерді бастаймыз
  if (!localStorage.getItem(LS_KEY)) {{
    localStorage.setItem(LS_KEY, Date.now().toString());
  }}

  function tick() {{
    const stored = localStorage.getItem(LS_KEY);
    const elapsed = stored ? Math.floor((Date.now()-parseInt(stored,10))/1000) : 0;
    const left = Math.max(0, TOTAL - elapsed);
    tDisp.textContent = fmt(left);
    tBox.className = left<=0?'done':left<=60?'red':left<=300?'yellow':'';
    if (left===300) setBar('⚠️ 5 минут қалды!','#FAEEDA','#EF9F27','#854F0B');
    if (left===60)  setBar('🔴 1 минут қалды! Жауаптарыңызды тексеріңіз.','#FCEBEB','#E24B4A','#A32D2D');
    if (left<=0) {{
      clearInterval(timerID);
      tDisp.textContent='00:00';
      setBar('⏰ Уақыт бітті! Тапсыру батырмасын басыңыз.','#FCEBEB','#E24B4A','#A32D2D');
      // Streamlit-ке хабар береміз
      window.parent.postMessage({{type:'reading_timeout', session:SESSION}}, '*');
    }}
  }}
  timerID = setInterval(tick, 500);
  tick();

  // Античит
  async function logEv(ev) {{
    try {{
      await fetch(SB_URL+'/rest/v1/anticheat_events',
        {{method:'POST', headers:H,
          body:JSON.stringify({{
            student_name: SESSION,
            session_id: SESSION,
            event_type: 'reading_'+ev,
            blur_count: blurCnt,
            paste_count: 0,
            annulled: 0,
          }})}});
    }} catch(e) {{}}
  }}

  document.addEventListener('visibilitychange', ()=>{{
    if (document.hidden) {{
      blurCnt++;
      logEv('blur_'+blurCnt);
      if (blurCnt===1) setBar('⚠️ Ескерту! Басқа бетке өтпеңіз!','#FAEEDA','#EF9F27','#854F0B');
      else if (blurCnt===2) setBar('🔴 Қатаң ескерту! Тағы шықсаңыз мұғалімге хабарланады!','#FCEBEB','#E24B4A','#A32D2D');
      else setBar('🚨 Тест барысы мұғалімге хабарланды!','#FCEBEB','#E24B4A','#A32D2D');
    }}
  }});

  logEv('start');
}})();
</script>
"""


# ─────────────────────────────────────────
# СҰРАҚ РЕНДЕРЛЕУ
# ─────────────────────────────────────────

def render_question(q: dict, q_num: int, answers: dict) -> None:
    """Бір сұрақты Streamlit виджеті ретінде көрсетеді."""
    qtype   = q.get("question_type", "mcq")
    qtext   = q.get("question_text", "")
    qid     = str(q["id"])
    options = q.get("options_json") or []
    key     = f"q_{qid}"

    st.markdown(f"**{q_num}.** {qtext}")

    if qtype == "mcq":
        opts = ["— Таңдаңыз —"] + options
        prev = answers.get(qid, "")
        idx  = opts.index(prev) if prev in opts else 0
        val  = st.selectbox("", opts, index=idx,
                            key=key, label_visibility="collapsed")
        if val != "— Таңдаңыз —":
            answers[qid] = val

    elif qtype in ("true_false", "tfng"):
        opts = ["True", "False", "Not Given"]
        prev = answers.get(qid, None)
        idx  = opts.index(prev) if prev in opts else None
        val  = st.radio("", opts, index=idx, horizontal=True,
                        key=key, label_visibility="collapsed")
        if val:
            answers[qid] = val

    elif qtype == "yes_no_ng":
        opts = ["Yes", "No", "Not Given"]
        prev = answers.get(qid, None)
        idx  = opts.index(prev) if prev in opts else None
        val  = st.radio("", opts, index=idx, horizontal=True,
                        key=key, label_visibility="collapsed")
        if val:
            answers[qid] = val

    elif qtype in ("fill_blank", "short_answer"):
        prev = answers.get(qid, "")
        val  = st.text_input("", value=prev, placeholder="Жауабыңызды жазыңыз",
                             key=key, label_visibility="collapsed")
        if val.strip():
            answers[qid] = val.strip()

    elif qtype == "matching":
        # Matching: options тізімінен таңдайды
        opts = ["— Таңдаңыз —"] + options
        prev = answers.get(qid, "")
        idx  = opts.index(prev) if prev in opts else 0
        val  = st.selectbox("", opts, index=idx,
                            key=key, label_visibility="collapsed")
        if val != "— Таңдаңыз —":
            answers[qid] = val

    else:
        # Fallback: text input
        prev = answers.get(qid, "")
        val  = st.text_input("", value=prev, key=key,
                             label_visibility="collapsed")
        if val.strip():
            answers[qid] = val.strip()

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)


# ─────────────────────────────────────────
# НЕГІЗГІ БӨЛІМ
# ─────────────────────────────────────────

st.title("📖 IELTS Reading Mock Test")
st.caption("Тесті мұқият оқып, барлық сұрақтарға жауап беріңіз.")
st.markdown("---")

# 1. Атын таңдау
st.subheader("1. Атыңызды таңдаңыз")
student_names = fetch_student_names()
if student_names:
    student_name = st.selectbox(
        "", ["— Атыңызды таңдаңыз —"] + student_names,
        label_visibility="collapsed"
    )
    if student_name == "— Атыңызды таңдаңыз —":
        student_name = ""
else:
    student_name = st.text_input(
        "", placeholder="Мысалы: Айгерім Сейтқали",
        label_visibility="collapsed"
    )

# 2. Тест таңдау
st.subheader("2. Тестті таңдаңыз")
tests = fetch_active_tests()

if not tests:
    st.info("⏳ Қазір белсенді тест жоқ. Мұғалімді күтіңіз.")
    st.stop()

test_options = {f"{t['title']}": t for t in tests}
selected_title = st.selectbox(
    "", ["— Тестті таңдаңыз —"] + list(test_options.keys()),
    label_visibility="collapsed"
)

if not student_name.strip() or selected_title == "— Тестті таңдаңыз —":
    st.info("Атыңызды және тестті таңдаңыз.")
    st.stop()

selected_test = test_options[selected_title]
test_id       = selected_test["id"]

# Session keys
skey      = f"reading_{student_name.strip().replace(' ','_')}_{test_id}"
done_key  = f"{skey}_done"
ans_key   = f"{skey}_answers"
att_key   = f"{skey}_attempt_id"

st.session_state.setdefault(done_key, False)
st.session_state.setdefault(ans_key,  {})

# Тест деректерін тарту
test_data = fetch_test_data(test_id)
if not test_data or not test_data["sections"]:
    st.error("Тест деректері жүктелмеді. Мұғалімге хабарлаңыз.")
    st.stop()

# Барлық сұрақтарды тізімге жинаймыз
all_questions = []
for sec in test_data["sections"]:
    for q in sec.get("questions", []):
        all_questions.append(q)
total_q = len(all_questions)

# Attempt жасау (бірінші рет)
if att_key not in st.session_state:
    attempt = fetch_attempt(test_id, student_name.strip())
    # Қайта тапсыру рұқсат — жаңа attempt жасаймыз
    new_id = create_attempt(test_id, student_name.strip())
    st.session_state[att_key] = new_id

attempt_id = st.session_state[att_key]

# ── НӘТИЖЕ БЕТІ ──
if st.session_state[done_key]:
    answers = st.session_state[ans_key]
    score   = sum(1 for q in all_questions
                  if check_answer(q, answers.get(str(q["id"]), "")))
    band    = score_to_band(score)
    show_result(score, total_q, band, all_questions, answers)

    if st.button("🔄 Қайта тапсыру", type="secondary"):
        for k in [done_key, ans_key, att_key]:
            st.session_state.pop(k, None)
        fetch_active_tests.clear()
        st.rerun()
    st.stop()

# ── ТЕСТ БЕТІ ──
st.markdown("---")

# Таймер iframe
components.html(
    build_reading_timer_html(
        session_id=skey,
        total_seconds=READING_SECONDS,
        sb_url=st.secrets["supabase"]["url"],
        sb_key=st.secrets["supabase"]["key"],
    ),
    height=60,
)

st.markdown(
    f"<p style='color:#555;font-size:13px;'>📝 Барлығы <b>{total_q}</b> сұрақ</p>",
    unsafe_allow_html=True,
)
st.markdown("---")

answers = st.session_state[ans_key]

# Секция + сұрақтарды рендерлейміз
q_num = 1
for sec in test_data["sections"]:
    sec_title = sec.get("title") or f"Бөлім {sec['order_num']}"
    passage   = sec.get("passage_text", "")
    questions = sec.get("questions", [])

    if not questions:
        continue

    # Екі баған: сол — мәтін, оң — сұрақтар
    col_text, col_qs = st.columns([1, 1], gap="large")

    with col_text:
        st.markdown(f"### 📄 {sec_title}")
        if passage:
            st.markdown(
                f"<div style='background:#F8F9FA;border-left:4px solid #639922;"
                f"border-radius:8px;padding:16px 18px;font-size:14px;"
                f"line-height:1.8;max-height:600px;overflow-y:auto;'>"
                f"{passage.replace(chr(10), '<br>')}</div>",
                unsafe_allow_html=True,
            )

    with col_qs:
        st.markdown(f"### ❓ Сұрақтар")
        for q in questions:
            render_question(q, q_num, answers)
            q_num += 1

    st.markdown("---")

# Прогресс
answered = sum(1 for q in all_questions
               if answers.get(str(q["id"]), "").strip())
st.markdown(
    f"<p style='color:#555;'>✏️ Жауап берілді: <b>{answered}</b> / {total_q}</p>",
    unsafe_allow_html=True,
)

if answered < total_q:
    st.warning(f"⚠️ Әлі {total_q - answered} сұраққа жауап берілмеген.")

# Тапсыру батырмасы
sub_col, _ = st.columns([2, 3])
with sub_col:
    if st.button("✅ Тестті тапсыру", type="primary",
                 use_container_width=True, key=f"submit_{skey}"):
        # Нәтижені есептеп DB-ге жазамыз
        score = sum(1 for q in all_questions
                    if check_answer(q, answers.get(str(q["id"]), "")))
        band  = score_to_band(score)
        ok    = submit_attempt(attempt_id, answers, score, band)
        if ok:
            st.session_state[done_key] = True
            st.rerun()
        else:
            st.error("❌ Сақтауда қате болды. Қайта басыңыз.")
