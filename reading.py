"""
reading.py — TEN IELTS Reading Mock Test
Streamlit + Supabase
"""
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
from utils import get_supabase

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
    try:
        res = (get_supabase().table("tests")
               .select("*")
               .eq("type", "reading")
               .eq("is_active", True)
               .order("created_at")
               .execute())
        return res.data or []
    except Exception:
        return []


@st.cache_data(ttl=30)
def fetch_all_attempts(student_name: str) -> dict:
    """Оқушының барлық тесттер бойынша соңғы attempt-ін {test_id: attempt} форматында қайтарады."""
    try:
        res = (get_supabase().table("test_attempts")
               .select("*")
               .eq("student_name", student_name)
               .order("submitted_at", desc=True)
               .execute())
        latest = {}
        for a in (res.data or []):
            tid = a.get("test_id")
            if tid not in latest:
                latest[tid] = a
        return latest
    except Exception:
        return {}


def fetch_test_data(test_id: int) -> dict | None:
    try:
        sections_res = (get_supabase().table("test_sections")
                        .select("*").eq("test_id", test_id)
                        .order("order_num").execute())
        sections = sections_res.data or []
        for sec in sections:
            q_res = (get_supabase().table("questions")
                     .select("*").eq("section_id", sec["id"])
                     .order("order_num").execute())
            sec["questions"] = q_res.data or []
        return {"sections": sections}
    except Exception:
        return None


def create_attempt(test_id: int, student_name: str) -> int | None:
    try:
        res = (get_supabase().table("test_attempts")
               .insert({"test_id": test_id, "student_name": student_name,
                        "started_at": datetime.now().isoformat()})
               .execute())
        return res.data[0]["id"] if res.data else None
    except Exception:
        return None


def submit_attempt(attempt_id: int, answers: dict, score: int, band: float) -> bool:
    try:
        get_supabase().table("test_attempts").update({
            "answers_json": answers, "score": score,
            "band": band, "submitted_at": datetime.now().isoformat(),
        }).eq("id", attempt_id).execute()
        return True
    except Exception:
        return False


# ─────────────────────────────────────────
# BAND ЕСЕПТЕУ
# ─────────────────────────────────────────

BAND_TABLE = {
    40: 9.0, 39: 8.5, 38: 8.5, 37: 8.0, 36: 8.0,
    35: 7.5, 34: 7.0, 33: 6.5, 32: 6.5, 31: 6.0,
    30: 6.0, 29: 5.5, 28: 5.5, 27: 5.0, 26: 5.0,
    25: 5.0, 24: 4.5, 23: 4.5, 22: 4.0, 21: 4.0,
    20: 4.0, 19: 3.5, 18: 3.5, 17: 3.0, 16: 3.0,
}

def score_to_band(score: int) -> float:
    return BAND_TABLE.get(max(0, min(40, score)), 2.5)


def check_answer(q: dict, user_ans: str) -> bool:
    correct = str(q.get("correct_answer", "")).strip().lower()
    user    = str(user_ans or "").strip().lower()
    if not user:
        return False
    if q.get("question_type") in ("fill_blank", "short_answer"):
        return user in [a.strip() for a in correct.split("|")]
    return user == correct


def band_color(band):
    try:
        b = float(band)
        if b >= 7:   return "#27500A", "#EAF3DE"
        elif b >= 6: return "#854F0B", "#FAEEDA"
        else:        return "#A32D2D", "#FCEBEB"
    except Exception:
        return "#555", "#F4F4F4"


# ─────────────────────────────────────────
# ТАЙМЕР HTML
# ─────────────────────────────────────────

def build_reading_timer_html(session_id: str, total_seconds: int,
                              sb_url: str, sb_key: str) -> str:
    mins = total_seconds // 60
    return f"""
<style>
*{{box-sizing:border-box;margin:0;padding:0;font-family:sans-serif;}}
body{{background:transparent;padding:4px 0;}}
#tw{{display:flex;align-items:center;gap:10px;}}
#tb{{background:#EAF3DE;border:1.5px solid #639922;border-radius:12px;
     padding:6px 16px;text-align:center;min-width:90px;transition:background .5s,border-color .5s;}}
#tl{{font-size:10px;color:#3B6D11;text-transform:uppercase;margin-bottom:1px;}}
#td{{font-size:22px;font-weight:600;color:#27500A;letter-spacing:1px;}}
#tb.yellow{{background:#FAEEDA;border-color:#EF9F27;}}
#tb.yellow #tl{{color:#854F0B;}}
#tb.yellow #td{{color:#633806;}}
#tb.red{{background:#FCEBEB;border-color:#E24B4A;}}
#tb.red #tl{{color:#A32D2D;}}
#tb.red #td{{color:#501313;}}
#tb.done{{background:#F09595;border-color:#E24B4A;animation:pulse 1s ease-in-out infinite;}}
@keyframes pulse{{0%,100%{{transform:scale(1);}}50%{{transform:scale(1.04);}}}}
#sb{{flex:1;padding:8px 14px;border-radius:8px;background:#EAF3DE;
     border-left:4px solid #639922;font-size:13px;color:#3B6D11;}}
</style>
<div id="tw">
  <div id="tb"><div id="tl">Уақыт</div><div id="td">{mins:02d}:00</div></div>
  <div id="sb">📖 Тест басталды. Сәттілік!</div>
</div>
<script>
(function(){{
  const TOTAL={total_seconds}, LS="rs_{session_id}";
  const tb=document.getElementById('tb'),
        td=document.getElementById('td'),
        sb=document.getElementById('sb');
  let blur=0;
  if(!localStorage.getItem(LS)) localStorage.setItem(LS,Date.now().toString());
  function fmt(s){{return String(Math.floor(s/60)).padStart(2,'0')+':'+String(s%60).padStart(2,'0');}}
  function bar(m,bg,bc,c){{sb.textContent=m;sb.style.background=bg;sb.style.borderLeftColor=bc;sb.style.color=c;}}
  setInterval(function(){{
    const e=Math.floor((Date.now()-parseInt(localStorage.getItem(LS)||Date.now(),10))/1000);
    const l=Math.max(0,TOTAL-e);
    td.textContent=fmt(l);
    tb.className=l<=0?'done':l<=60?'red':l<=300?'yellow':'';
    if(l===300) bar('⚠️ 5 минут қалды!','#FAEEDA','#EF9F27','#854F0B');
    if(l===60)  bar('🔴 1 минут қалды!','#FCEBEB','#E24B4A','#A32D2D');
    if(l<=0)    bar('⏰ Уақыт бітті! Тапсыру батырмасын басыңыз.','#FCEBEB','#E24B4A','#A32D2D');
  }},500);
  document.addEventListener('visibilitychange',function(){{
    if(!document.hidden) return;
    blur++;
    if(blur===1) bar('⚠️ Басқа бетке өтпеңіз!','#FAEEDA','#EF9F27','#854F0B');
    else if(blur===2) bar('🔴 Қатаң ескерту!','#FCEBEB','#E24B4A','#A32D2D');
    else bar('🚨 Белсенділік тіркелді!','#FCEBEB','#E24B4A','#A32D2D');
  }});
}})();
</script>
"""


# ─────────────────────────────────────────
# СҰРАҚ РЕНДЕРЛЕУ
# ─────────────────────────────────────────

def render_question(q: dict, q_num: int, answers: dict) -> None:
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
        val  = st.selectbox("", opts, index=idx, key=key, label_visibility="collapsed")
        if val != "— Таңдаңыз —":
            answers[qid] = val

    elif qtype in ("true_false", "tfng"):
        opts = ["True", "False", "Not Given"]
        prev = answers.get(qid, None)
        idx  = opts.index(prev) if prev in opts else None
        val  = st.radio("", opts, index=idx, horizontal=True, key=key, label_visibility="collapsed")
        if val:
            answers[qid] = val

    elif qtype == "yes_no_ng":
        opts = ["Yes", "No", "Not Given"]
        prev = answers.get(qid, None)
        idx  = opts.index(prev) if prev in opts else None
        val  = st.radio("", opts, index=idx, horizontal=True, key=key, label_visibility="collapsed")
        if val:
            answers[qid] = val

    elif qtype in ("fill_blank", "short_answer"):
        prev = answers.get(qid, "")
        val  = st.text_input("", value=prev, placeholder="Жауабыңызды жазыңыз",
                             key=key, label_visibility="collapsed")
        if val.strip():
            answers[qid] = val.strip()

    elif qtype == "matching":
        opts = ["— Таңдаңыз —"] + options
        prev = answers.get(qid, "")
        idx  = opts.index(prev) if prev in opts else 0
        val  = st.selectbox("", opts, index=idx, key=key, label_visibility="collapsed")
        if val != "— Таңдаңыз —":
            answers[qid] = val

    else:
        prev = answers.get(qid, "")
        val  = st.text_input("", value=prev, key=key, label_visibility="collapsed")
        if val.strip():
            answers[qid] = val.strip()

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)


# ─────────────────────────────────────────
# НӘТИЖЕ БЕТІ
# ─────────────────────────────────────────

def show_result_page(score: int, total: int, band: float,
                     questions: list, answers: dict):
    st.success("✅ Тест сәтті тапсырылды!")
    st.markdown(
        f"<h2 style='text-align:center;color:#1E88E5;'>🏆 Band Score: {band}</h2>",
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns(2)
    c1.metric("Дұрыс жауап", f"{score} / {total}")
    c2.metric("Band", band)
    st.markdown("---")
    st.subheader("📋 Жауаптар талдауы")
    for i, q in enumerate(questions, 1):
        user_ans = answers.get(str(q["id"]), "")
        correct  = check_answer(q, user_ans)
        icon     = "✅" if correct else "❌"
        with st.expander(f"{icon} Q{i}: {q['question_text'][:80]}"):
            st.markdown(f"**Сіздің жауабыңыз:** `{user_ans or '—'}`")
            st.markdown(f"**Дұрыс жауап:** `{q['correct_answer']}`")


# ─────────────────────────────────────────
# ТЕСТ КАРТОЧКАСЫ
# ─────────────────────────────────────────

def render_test_card(test: dict, attempt: dict | None):
    title   = test.get("title", "—")
    test_id = test["id"]

    if attempt and attempt.get("submitted_at"):
        score    = attempt.get("score", 0)
        band     = attempt.get("band", 0)
        date     = (attempt.get("submitted_at") or "")[:10]
        tc, bg   = band_color(band)

        st.markdown(f"""
        <div style="background:white;border:1px solid #E2E8F0;border-radius:14px;
                    padding:18px 20px;margin-bottom:4px;border-left:5px solid {tc};">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
            <div>
              <div style="font-size:15px;font-weight:600;color:#1E293B;">✅ {title}</div>
              <div style="font-size:12px;color:#64748B;margin-top:4px;">📅 {date}</div>
            </div>
            <div style="display:flex;align-items:center;gap:10px;">
              <div style="background:#F4F4F4;border-radius:8px;padding:6px 14px;text-align:center;">
                <div style="font-size:11px;color:#666;">Балл</div>
                <div style="font-size:18px;font-weight:700;">{score}/40</div>
              </div>
              <div style="background:{bg};border-radius:8px;padding:6px 14px;text-align:center;">
                <div style="font-size:11px;color:{tc};">Band</div>
                <div style="font-size:22px;font-weight:700;color:{tc};">{band}</div>
              </div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("📋 Нәтижені көру", key=f"view_{test_id}", use_container_width=True):
                st.session_state["selected_test"]  = test
                st.session_state["view_attempt"]   = attempt
                st.session_state["mode"]           = "result"
                st.rerun()
        with col2:
            if st.button("🔄 Қайта тапсыру", key=f"retry_{test_id}", use_container_width=True):
                st.session_state["selected_test"] = test
                st.session_state["mode"]          = "test"
                st.rerun()

    else:
        st.markdown(f"""
        <div style="background:white;border:1px solid #E2E8F0;border-radius:14px;
                    padding:18px 20px;margin-bottom:4px;border-left:5px solid #CBD5E0;">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <div>
              <div style="font-size:15px;font-weight:600;color:#1E293B;">⏳ {title}</div>
              <div style="font-size:12px;color:#94A3B8;margin-top:4px;">Тапсырылмаған</div>
            </div>
            <div style="background:#F1F5F9;border-radius:8px;padding:6px 16px;
                        font-size:13px;color:#64748B;">— / 40</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("▶️ Бастау", key=f"start_{test_id}",
                     use_container_width=True, type="primary"):
            st.session_state["selected_test"] = test
            st.session_state["mode"]          = "test"
            st.rerun()

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)


# ─────────────────────────────────────────
# НЕГІЗГІ ЛОГИКА
# ─────────────────────────────────────────

st.session_state.setdefault("mode", "home")
st.session_state.setdefault("selected_test", None)
st.session_state.setdefault("student_name", "")
st.session_state.setdefault("view_attempt", None)

mode = st.session_state["mode"]


# ══════════════════════════════
# БАСТАПҚЫ БЕТ
# ══════════════════════════════
if mode == "home":
    st.title("📖 IELTS Reading Mock Test")
    st.markdown("---")

    st.subheader("Атыңызды таңдаңыз")
    names = fetch_student_names()
    if names:
        sel = st.selectbox("", ["— Атыңызды таңдаңыз —"] + names,
                           label_visibility="collapsed", key="name_sel")
        student_name = "" if sel == "— Атыңызды таңдаңыз —" else sel
    else:
        student_name = st.text_input("", placeholder="Мысалы: Айгерім",
                                     label_visibility="collapsed")

    if not student_name.strip():
        st.info("Атыңызды таңдасаңыз тесттер пайда болады.")
        st.stop()

    st.session_state["student_name"] = student_name.strip()

    tests    = fetch_active_tests()
    attempts = fetch_all_attempts(student_name.strip())

    if not tests:
        st.info("⏳ Қазір белсенді тест жоқ.")
        st.stop()

    done  = sum(1 for t in tests if attempts.get(t["id"], {}).get("submitted_at"))
    total = len(tests)

    st.markdown(f"### Сәлем, **{student_name}**! 👋")
    st.markdown(
        f"<p style='color:#555;font-size:13px;margin-bottom:16px;'>"
        f"✅ Тапсырылды: <b>{done}</b> / {total}</p>",
        unsafe_allow_html=True,
    )

    for test in tests:
        render_test_card(test, attempts.get(test["id"]))


# ══════════════════════════════
# ТЕСТ БЕТІ
# ══════════════════════════════
elif mode == "test":
    selected_test = st.session_state.get("selected_test")
    student_name  = st.session_state.get("student_name", "")

    if not selected_test or not student_name:
        st.session_state["mode"] = "home"
        st.rerun()

    test_id  = selected_test["id"]
    skey     = f"r_{student_name.replace(' ','_')}_{test_id}"
    done_key = f"{skey}_done"
    ans_key  = f"{skey}_ans"
    att_key  = f"{skey}_att"

    st.session_state.setdefault(done_key, False)
    st.session_state.setdefault(ans_key, {})

    test_data = fetch_test_data(test_id)
    if not test_data or not test_data["sections"]:
        st.error("Тест деректері жүктелмеді.")
        st.stop()

    all_questions = [q for sec in test_data["sections"] for q in sec.get("questions", [])]
    total_q       = len(all_questions)

    if att_key not in st.session_state:
        st.session_state[att_key] = create_attempt(test_id, student_name)

    attempt_id = st.session_state[att_key]

    # ── Нәтиже беті ──
    if st.session_state[done_key]:
        answers = st.session_state[ans_key]
        score   = sum(1 for q in all_questions
                      if check_answer(q, answers.get(str(q["id"]), "")))
        band    = score_to_band(score)
        show_result_page(score, total_q, band, all_questions, answers)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🏠 Басты бетке", use_container_width=True):
                for k in [done_key, ans_key, att_key]:
                    st.session_state.pop(k, None)
                st.session_state["mode"] = "home"
                fetch_all_attempts.clear()
                st.rerun()
        with col2:
            if st.button("🔄 Қайта тапсыру", use_container_width=True):
                for k in [done_key, ans_key, att_key]:
                    st.session_state.pop(k, None)
                st.rerun()
        st.stop()

    # ── Тест беті ──
    col_title, col_back = st.columns([5, 1])
    with col_title:
        st.markdown(f"### 📖 {selected_test.get('title','')}")
    with col_back:
        if st.button("🏠 Басты бет", use_container_width=True):
            for k in [done_key, ans_key, att_key]:
                st.session_state.pop(k, None)
            st.session_state["mode"] = "home"
            st.rerun()

    components.html(
        build_reading_timer_html(
            session_id=skey,
            total_seconds=READING_SECONDS,
            sb_url=st.secrets["supabase"]["url"],
            sb_key=st.secrets["supabase"]["key"],
        ),
        height=60,
    )
    st.markdown("---")

    answers  = st.session_state[ans_key]
    sections = test_data["sections"]

    if len(sections) > 1:
        labels     = [s.get("title") or f"Passage {s['order_num']}" for s in sections]
        sel_p      = st.radio("📄 Passage:", labels, horizontal=True, key=f"pnav_{skey}")
        active     = [s for s in sections if (s.get("title") or f"Passage {s['order_num']}") == sel_p]
    else:
        active = sections

    q_offset = 0
    for sec in sections:
        qs = sec.get("questions", [])
        if sec not in active:
            q_offset += len(qs)
            continue
        passage = sec.get("passage_text", "")
        if not qs:
            continue

        col_t, col_q = st.columns([1, 1], gap="large")
        with col_t:
            st.markdown(f"#### 📄 {sec.get('title','')}")
            if passage:
                st.markdown(
                    f"<div style='background:#F8F9FA;border-left:4px solid #639922;"
                    f"border-radius:8px;padding:16px 18px;font-size:14px;"
                    f"line-height:1.8;max-height:600px;overflow-y:auto;'>"
                    f"{passage.replace(chr(10), '<br>')}</div>",
                    unsafe_allow_html=True,
                )
        with col_q:
            st.markdown("#### ❓ Сұрақтар")
            st.markdown(
                "<div style='max-height:600px;overflow-y:auto;padding-right:8px;'>",
                unsafe_allow_html=True,
            )
            for i, q in enumerate(qs):
                render_question(q, q_offset + i + 1, answers)
            st.markdown("</div>", unsafe_allow_html=True)

        q_offset += len(qs)
        st.markdown("---")

    answered = sum(1 for q in all_questions if answers.get(str(q["id"]), "").strip())
    st.markdown(
        f"<p style='color:#555;'>✏️ Жауап берілді: <b>{answered}</b> / {total_q}</p>",
        unsafe_allow_html=True,
    )
    if answered < total_q:
        st.warning(f"⚠️ Әлі {total_q - answered} сұраққа жауап берілмеген.")

    sub_col, _ = st.columns([2, 3])
    with sub_col:
        if st.button("✅ Тестті тапсыру", type="primary",
                     use_container_width=True, key=f"sub_{skey}"):
            score = sum(1 for q in all_questions
                        if check_answer(q, answers.get(str(q["id"]), "")))
            band  = score_to_band(score)
            if submit_attempt(attempt_id, answers, score, band):
                st.session_state[done_key] = True
                fetch_all_attempts.clear()
                st.rerun()
            else:
                st.error("❌ Сақтауда қате болды. Қайта басыңыз.")


# ══════════════════════════════
# НӘТИЖЕ КОЮ БЕТІ
# ══════════════════════════════
elif mode == "result":
    selected_test = st.session_state.get("selected_test")
    attempt       = st.session_state.get("view_attempt")
    student_name  = st.session_state.get("student_name", "")

    if not selected_test or not attempt:
        st.session_state["mode"] = "home"
        st.rerun()

    test_id       = selected_test["id"]
    answers       = attempt.get("answers_json") or {}
    score         = attempt.get("score", 0)
    band          = attempt.get("band", 0)
    test_data     = fetch_test_data(test_id)
    all_questions = [q for sec in (test_data or {}).get("sections", [])
                     for q in sec.get("questions", [])]

    show_result_page(score, len(all_questions), band, all_questions, answers)

    if st.button("🏠 Басты бетке", use_container_width=True):
        st.session_state["mode"]         = "home"
        st.session_state["view_attempt"] = None
        st.rerun()
