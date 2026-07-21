/* ==========================================================================
   [선생님 전용 설정 구역]
   실시간 AI 분석을 켜려면 아래 따옴표 안에 Google AI Studio에서 무료로
   발급받은 Gemini API 키를 붙여넣으세요. (https://aistudio.google.com/apikey)
   - 키가 비어 있으면("") 자동으로 '오프라인 간이 분석기'로 작동합니다.
   - 주의: 이 파일을 받은 사람은 누구나 키를 볼 수 있으므로,
     무료 등급 키만 사용하고 파일을 학급 외부에 공유하지 마세요.
   ========================================================================== */
const GEMINI_API_KEY = "";
/* [AI 모델 선택] 무료 한도가 다르니 학급 상황에 맞게 아래 한 줄만 바꾸면 됩니다.
   - "gemini-2.5-flash-lite" : 하루 약 1,000회 (현재 설정 · 학급 단위 사용 권장)
   - "gemini-2.5-flash"      : 하루 약 250회 (답변 품질 조금 더 높음)
   ※ 무료 한도는 구글이 변경할 수 있으니 정확한 수치는 AI 스튜디오에서 확인하세요. */
const GEMINI_MODEL = "gemini-2.5-flash-lite";

/* ===================== 크레딧 ===================== */
// 기획 및 설계: 정숙진 선생님
const CREATOR_NAME = "정숙진 선생님";
// 소속: 내리숲초등학교 교육과정부
const ORG_NAME = "내리숲초등학교 교육과정부";
// 푸터(메인 화면) 표기: 정숙진 교사
const FOOTER_CREDIT = "정숙진 교사";

/* ===================== 6가지 질문 유형 데이터 ===================== */
const QUESTION_TYPES = {
  "관찰 질문": {
    description: "주변 세계를 있는 그대로 관찰하고 사실적 내용을 확인하는 질문입니다.",
    emoji: "🔍", badgeColor: "var(--blue-500)",
    growthStage: "1학년 [관찰] '무엇이 보일까?'", baseStage: "B (Books) - 준비하기",
    detail: "책이나 자료를 자세히 살펴보면 답을 바로 찾을 수 있는 '기초 체력' 같은 질문이에요. '누가, 언제, 어디서, 무엇을 했지?'를 생각하며 만들어요.",
    method: { name: "까바 놀이", tip: "짝이 말한 문장을 그대로 받아 '~까?'로 끝나는 질문으로 바꿔 보아요. 상대의 말을 귀 기울여 듣고 사실을 정확히 파악하는 힘이 자라나요." },
    examples: ["그림책 표지 속 주인공은 무엇을 손에 들고 있나요?","생성형 AI가 작동할 때 가장 먼저 일어나는 현상은 무엇인가요?","우리 지역에 있는 국가유산에는 어떤 것들이 있나요?"]
  },
  "공감 질문": {
    description: "경험 속 감정을 알아차리고 상황에 공감하며 상상해 보는 질문입니다.",
    emoji: "🔮", badgeColor: "var(--purple-500)",
    growthStage: "2학년 [공감] '어떤 느낌일까?'", baseStage: "B (Books) - 탐구하기",
    detail: "나와 타인의 마음을 연결해 주는 생각의 날개예요. 주인공의 마음에 공감하거나 가상의 상황을 상상해 보는 따뜻한 질문이랍니다. 눈에 보이는 사실에서 출발해 보이지 않는 마음과 의미로 나아가는, 사실적 질문에서 개념적 질문으로 넘어가는 다리 역할을 해요.",
    method: { name: "까만 놀이", tip: "답하지 않고 서로 질문만 주고받으며 이어 가요. 정답 대신 다양한 느낌과 생각의 방향을 마음껏 펼칠 수 있어요." },
    examples: ["만약 내가 주인공이었다면 그 순간 어떤 느낌이 들었을까요?","만약 윤리적 기준이 없는 미래 사회로 간다면 우리의 하루는 어떻게 변할까요?","인공지능이 감정을 느끼게 된다면 어떤 일이 벌어질까요?"]
  },
  "해석 질문": {
    description: "경험과 텍스트를 해석하며 숨겨진 의미와 까닭을 파악하는 질문입니다.",
    emoji: "💡", badgeColor: "var(--indigo-500)",
    growthStage: "3학년 [해석] '무슨 의미일까?'", baseStage: "A (Advance) - 탐구하기",
    detail: "단순한 예/아니오 대답을 넘어, 생각의 주머니를 활짝 열어주는 만능 질문이에요. 정보들 사이의 관계와 원리를 발견하고 개념적 이해를 도출합니다.",
    method: { name: "질문 꼬리잡기", tip: "친구의 답을 듣고 '왜?', '어떻게?'로 다시 물으며 질문을 이어 가요. 겉으로 보이지 않는 까닭과 숨은 의미를 깊이 파고들 수 있어요." },
    examples: ["인공지능의 데이터 수집과 처리 과정에서 왜 개인정보 침해 문제가 발생하는 걸까요?","문화유산 속에 숨겨진 옛사람들의 지혜를 우리는 어떻게 발견할 수 있을까요?","책 속의 주인공은 왜 그런 중요한 결정을 내렸고 그것이 지닌 의미는 무엇일까요?"]
  },
  "표현 질문": {
    description: "탐구한 내용과 자신의 생각을 유기적으로 종합하여 표현하는 질문입니다.",
    emoji: "🧱", badgeColor: "var(--amber-500)",
    growthStage: "4학년 [표현] '어떻게 말할까?'", baseStage: "S (Share) - 정리하기",
    detail: "따로따로 흩어져 있던 정보 조각들을 끈끈하게 엮어서 하나의 큰 보물지도로 만드는 질문이에요. 탐구한 내용을 자신의 말과 글로 구조화합니다.",
    method: { name: "질문 형성 기법(QFT)", tip: "질문을 최대한 많이 만들고 → 열린/닫힌 질문으로 분류하고 → 다듬고 → 중요한 순서를 정해요. 흩어진 생각이 차곡차곡 구조화돼요." },
    examples: ["문화유산이 과거와 현재를 이어주는 다리라는 것을 설명하기 위해 한 문장으로 정리해 볼까요?","이 책의 전체 내용을 관통하는 핵심 개념 두 가지를 연결하면 어떤 지혜를 얻을 수 있을까요?","오늘 알아본 다양한 인공지능 사건들의 공통적인 원인은 무엇인가요?"]
  },
  "판단 질문": {
    description: "대상의 행동이나 말에 대해 근거를 바탕으로 비판적으로 판단하는 질문입니다.",
    emoji: "⚖️", badgeColor: "var(--red-500)",
    growthStage: "5학년 [판단] '타당할까?'", baseStage: "S (Share) - 정리하기",
    detail: "옳고 그름을 따져보고, 나만의 멋진 기준을 세우는 생각의 뼈대예요. 다양한 관점과 가치를 비교·성찰하여 비판적으로 타당성을 검토합니다.",
    method: { name: "토론 질문 만들기", tip: "찬성과 반대로 나뉠 수 있는 질문을 만들어 논제를 정해요. 근거를 들어 타당한지 따져 보는 비판적 사고의 힘이 자라요." },
    examples: ["인공지능이 그린 그림에 저작권을 인정해 주는 것은 정말 타당할까요?","주인공이 친구들을 구하기 위해 법을 어긴 행동은 과연 올바른 선택이었을까요?","지역 개발을 위해 문화유산을 다른 곳으로 옮기는 결정은 정당할까요?"]
  },
  "실천 질문": {
    description: "배운 내용을 삶과 사회로 연결하여 무엇을 바꿀지 모색하는 질문입니다.",
    emoji: "🌱", badgeColor: "var(--emerald-500)",
    growthStage: "6학년 [실천] '무엇을 바꿀까?'", baseStage: "E (Ethics) - 실천하기",
    detail: "머리로 배운 지식을 손과 발로 움직이게 하는 마법 같은 질문이에요. 정해진 정답 없이 배움을 실천으로 전이시키는 최상위 단계입니다.",
    method: { name: "까주 놀이", tip: "질문하고 → 답을 듣고 → 그 답으로 다시 질문해요. '그럼 어떻게 바꿀 수 있을까?'까지 나아가며 배움을 행동으로 연결해요." },
    examples: ["올바른 디지털 미래를 위해 오늘부터 나와 우리 학교가 바꿀 수 있는 행동은 무엇인가요?","슬퍼하는 친구에게 따뜻한 위로를 전하기 위해 내가 실천할 수 있는 행동 약속은 무엇인가요?","우리 지역의 소중한 문화유산을 널리 지키고 알리기 위해 어떤 캠페인을 벌일 수 있을까요?"]
  }
};

/* ===================== 학년군별 퀴즈 은행 (각 8문항) ===================== */
const QUIZ_OPTIONS = ["관찰 질문","공감 질문","판단 질문","실천 질문","표현 질문","해석 질문"];
const QUIZ_BANK_BY_GRADE = {
  low: [
    { question:"그림책 표지에 나온 동물은 모두 몇 마리인가요?", answer:"관찰 질문", hint:"눈으로 자세히 보고 세어 보면 바로 답을 찾을 수 있는 질문이에요." },
    { question:"만약 내가 흥부라면, 다친 제비를 보았을 때 어떤 마음이 들었을까요?", answer:"공감 질문", hint:"내가 주인공이 되었다고 상상하며 마음을 느껴 보는 질문이에요." },
    { question:"주인공은 왜 비 오는 날 강아지에게 우산을 씌워 주었을까요?", answer:"해석 질문", hint:"'왜'라는 말로 행동에 숨은 까닭을 찾아보는 질문이에요." },
    { question:"오늘 읽은 이야기를 딱 한 문장으로 말하면 뭐라고 할 수 있을까요?", answer:"표현 질문", hint:"알게 된 내용을 나의 말로 정리해서 나타내 보는 질문이에요." },
    { question:"친구의 장난감을 허락 없이 가져가는 것은 옳은 행동일까요?", answer:"판단 질문", hint:"옳은지 그른지 까닭을 들어 따져 보는 질문이에요." },
    { question:"우리 교실을 깨끗하게 만들기 위해 내가 오늘부터 할 수 있는 일은 무엇일까요?", answer:"실천 질문", hint:"배운 것을 나의 행동으로 직접 옮겨 보게 하는 질문이에요." },
    { question:"만약 우리 반 화분이 말을 할 수 있다면 우리에게 뭐라고 말할까요?", answer:"공감 질문", hint:"'만약'이라고 상상하며 다른 존재의 마음이 되어 보는 질문이에요." },
    { question:"이야기 속에서 토끼는 어디에 살고 있나요?", answer:"관찰 질문", hint:"책 속에서 사실을 그대로 찾아 확인하는 질문이에요." }
  ],
  mid: [
    { question:"우리 고장의 옛날 지도와 지금 지도를 비교하면 무엇이 달라졌나요?", answer:"관찰 질문", hint:"자료를 자세히 살펴보고 사실을 그대로 확인하는 질문이에요." },
    { question:"만약 내가 조선 시대 어린이가 되어 하루를 산다면 어떤 기분일까요?", answer:"공감 질문", hint:"상황을 바꾸어 가정하고 그 속의 마음을 상상해 보는 질문이에요." },
    { question:"옛날 사람들은 왜 마을 입구에 장승을 세웠을까요?", answer:"해석 질문", hint:"'왜'를 활용해 겉으로 보이지 않는 까닭과 의미를 찾아가는 질문이에요." },
    { question:"식물의 한살이를 관찰한 내용을 그림과 글로 어떻게 정리하면 좋을까요?", answer:"표현 질문", hint:"탐구한 내용을 나만의 방법으로 구조화해서 나타내는 질문이에요." },
    { question:"숙제를 안 한 친구를 도와주려고 내 답을 그대로 보여 주는 것은 진짜 도움일까요?", answer:"판단 질문", hint:"어떤 행동이 옳은지 근거를 들어 스스로 따져 보는 질문이에요." },
    { question:"학교 앞 횡단보도를 더 안전하게 만들기 위해 우리 반이 할 수 있는 일은 무엇일까요?", answer:"실천 질문", hint:"배운 내용을 우리 학교와 마을의 실제 행동으로 연결하는 질문이에요." },
    { question:"이야기의 처음과 끝을 연결해 보면, 주인공의 마음이 어떻게 변했다고 정리할 수 있을까요?", answer:"표현 질문", hint:"여러 부분의 내용을 엮어서 하나의 문장으로 종합하는 질문이에요." },
    { question:"만약 우리 고장에서 갑자기 물이 나오지 않는다면 하루가 어떻게 달라질까요?", answer:"공감 질문", hint:"'만약'으로 상황을 가정하고 그 변화를 상상해 보는 질문이에요." }
  ],
  high: [
    { question:"만약 지구가 중력을 잃어버리고 모두가 둥둥 떠다니게 된다면 우리 교실은 어떻게 변할까요?", answer:"공감 질문", hint:"상황을 다르게 가정하고 마음을 이입하며 상상해보는 질문이에요." },
    { question:"우리가 살고 있는 경기도에 위치한 유네스코 세계문화유산의 이름들은 무엇인가요?", answer:"관찰 질문", hint:"지역 문화유산의 실태와 이름을 있는 그대로 관찰하고 확인하는 질문이에요." },
    { question:"기후 변화로 동물들이 살 곳을 잃어가는 환경 문제를 해결하기 위해, 우리 집과 학교에서 오늘 당장 시작할 수 있는 착한 습관은 무엇일까요?", answer:"실천 질문", hint:"배운 가치를 나의 삶, 우리의 일상에 적용하고 실제로 행동에 옮기게 만드는 질문이에요." },
    { question:"인간보다 뛰어난 인공지능이 등장했을 때, 윤리적 제동 장치 없이 인공지능의 개발 속도만 높이는 연구 방향은 정당할까요?", answer:"판단 질문", hint:"행동이나 정책의 타당성에 대해 스스로 가치 판단을 내리고 근거를 찾도록 돕는 질문이에요." },
    { question:"생성형 AI가 만들어내는 가짜 뉴스는 왜 위험하며, 우리는 디지털 세상에서 왜 팩트체크를 꼼꼼히 거쳐야 할까요?", answer:"해석 질문", hint:"'왜'를 활용해 숨겨진 의미와 깊이 있는 이유를 해석해 나가는 열린 질문이에요." },
    { question:"인공지능 시대에 필요한 여러 능력을 조사한 뒤, 이를 하나로 엮어 '미래 인재'를 한 문장으로 정의한다면 무엇일까요?", answer:"표현 질문", hint:"탐구한 여러 개념을 종합하여 자신의 언어로 구조화하는 질문이에요." },
    { question:"역사적 사건을 다룬 영화가 재미를 위해 사실과 다르게 표현하는 것은 허용될 수 있을까요?", answer:"판단 질문", hint:"서로 다른 가치가 부딪히는 상황에서 타당성을 비판적으로 검토하는 질문이에요." },
    { question:"우리 지역의 사라져 가는 전통 시장을 살리기 위해 초등학생인 우리가 시작할 수 있는 캠페인은 무엇일까요?", answer:"실천 질문", hint:"배움을 지역 사회의 실제 변화를 만드는 행동으로 전이시키는 질문이에요." }
  ]
};

/* ===================== 질문 놀이터: 숲속 보물 아이템 도감 ===================== */
const ITEMS = [
  { id:'acorn',     name:'도토리',        emoji:'🌰', rarity:'common' },
  { id:'mushroom',  name:'숲속 버섯',     emoji:'🍄', rarity:'common' },
  { id:'leaf',      name:'반짝 나뭇잎',   emoji:'🍃', rarity:'common' },
  { id:'flower',    name:'들꽃',          emoji:'🌼', rarity:'common' },
  { id:'clover',    name:'네잎클로버',    emoji:'🍀', rarity:'rare' },
  { id:'butterfly', name:'숲의 나비',     emoji:'🦋', rarity:'rare' },
  { id:'firefly',   name:'반딧불이',      emoji:'✨', rarity:'rare' },
  { id:'squirrel',  name:'다람쥐 친구',   emoji:'🐿️', rarity:'rare' },
  { id:'owl',       name:'지혜의 부엉이', emoji:'🦉', rarity:'legend' },
  { id:'dew',       name:'무지개 이슬',   emoji:'🌈', rarity:'legend' },
  { id:'gem',       name:'숲의 보석',     emoji:'💎', rarity:'legend' },
  { id:'crown',     name:'질문왕 왕관',   emoji:'👑', rarity:'legend' }
];
const RARITY_LABEL = { common:'일반', rare:'희귀', legend:'전설' };

// 탐험가 등급 (모은 QP에 따라 성장)
const RANKS = [
  { min:1000, name:'👑 전설의 질문왕' },
  { min:500,  name:'🦉 지혜의 탐험대장' },
  { min:250,  name:'🍀 숲속 탐험가' },
  { min:100,  name:'🌰 도토리 수집가' },
  { min:0,    name:'🌱 새싹 탐험가' }
];
const getRank = (p) => RANKS.find(r => p >= r.min).name;

// 보상 뽑기: 연속 정답(콤보)이 쌓일수록 희귀·전설 확률 상승
function rollItem(streak) {
  let w = { legend:5, rare:25 };            // 기본: 전설 5% / 희귀 25% / 일반 70%
  if (streak >= 5) w = { legend:30, rare:45 };   // 5콤보: 전설 30% / 희귀 45%
  else if (streak >= 3) w = { legend:15, rare:40 }; // 3콤보: 전설 15% / 희귀 40%
  const roll = Math.random() * 100;
  const rarity = roll < w.legend ? 'legend' : roll < w.legend + w.rare ? 'rare' : 'common';
  const pool = ITEMS.filter(i => i.rarity === rarity);
  return pool[Math.floor(Math.random() * pool.length)];
}

// 보물 주머니 (태블릿별 localStorage 저장)
const INV_KEY = 'naerisoop_playground_inventory';
let inv = { points: 0, bestStreak: 0, items: {} };
function loadInv() {
  try {
    const raw = localStorage.getItem(INV_KEY);
    if (raw) inv = { points:0, bestStreak:0, items:{}, ...JSON.parse(raw) };
  } catch (e) { /* 첫 방문 */ }
}
function saveInv() {
  try { localStorage.setItem(INV_KEY, JSON.stringify(inv)); }
  catch (e) { console.error('보물 주머니 저장 실패:', e); }
}

/* ===================== 상태 ===================== */
const STORAGE_KEY = 'naerisoop_saved_questions';
const state = {
  gradeLevel: 'mid',
  isLoading: false,
  analysisResult: null,
  isFallbackActive: false,
  fallbackReason: null, // 'no_key'(API 키 미설정) | 'network'(실제 접속 실패) 구분
  savedQuestions: [],
  selectedForSummary: [],
  generalization: '',
  isSummarizing: false,
  quizSet: [],
  quizIndex: 0,
  quizPicked: null,
  quizSubmitted: false,
  quizScore: 0,
  quizHint: false,
  streak: 0,        // 🔥 연속 정답 콤보
  roundCorrect: 0,  // 이번 라운드 정답 수 (퍼펙트 보너스 판정)
  lastDrop: null,   // 방금 획득한 보물 정보
  pouchOpen: false  // 보물 주머니 열림 여부
};

/* ===================== 유틸 ===================== */
const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
const shuffleArray = (arr) => {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
};
let toastTimer;
function showToast(msg) {
  $('#toastMsg').textContent = msg;
  const t = $('#toast');
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 3000);
}

/* ===================== 저장소 (태블릿별 localStorage) ===================== */
function loadForest() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) state.savedQuestions = JSON.parse(raw);
  } catch (e) { state.savedQuestions = []; }
}
function persistForest() {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state.savedQuestions)); }
  catch (e) { console.error('저장 실패:', e); }
}

/* ===================== Gemini API 호출 ===================== */
async function callGemini(systemPrompt, userQuery, wantJson) {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=${GEMINI_API_KEY}`;
  const payload = {
    contents: [{ parts: [{ text: userQuery }] }],
    systemInstruction: { parts: [{ text: systemPrompt }] }
  };
  if (wantJson) payload.generationConfig = { responseMimeType: "application/json" };

  let delay = 1000;
  for (let i = 0; i < 3; i++) {
    try {
      const res = await fetch(url, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
      if (res.ok) {
        const data = await res.json();
        return data.candidates?.[0]?.content?.parts?.[0]?.text || '';
      }
    } catch (e) { /* 재시도 */ }
    if (i < 2) { await new Promise(r => setTimeout(r, delay)); delay *= 2; }
  }
  throw new Error('API 요청 실패');
}

/* ===================== 질문 분석 ===================== */
const LOADING_MESSAGES = [
  "🌱 질문 씨앗을 화분에 심고 분석하는 중...",
  "🔍 내리숲 질문 필터로 알맞은 유형을 찾는 중...",
  "✨ 더 깊고 푸른 질문으로 다듬는 중...",
  "🌲 푸른 지혜를 가득 담은 열매가 열리는 중..."
];
let loadingTimer, loadingStep = 0;

async function analyzeQuestion() {
  const input = $('#inputQuestion').value.trim();
  if (!input) { showToast("다듬고 싶은 질문을 먼저 입력해 주세요!"); return; }
  if (state.isLoading) return;

  state.isLoading = true;
  state.isFallbackActive = false;
  $('#btnAnalyze').disabled = true;
  $('#btnAnalyze').innerHTML = '⏳ 질문 가꾸는 중...';
  renderLoading();

  const gradeText = state.gradeLevel === 'low' ? '1~2학년군 (저학년)' : state.gradeLevel === 'mid' ? '3~4학년군 (중학년)' : '5~6학년군 (고학년)';
  const systemPrompt = `너는 경기도교육청의 질문 기반 탐구수업 가이드라인과 내리숲초등학교의 질문 성장 서사를 지도하는 친절하고 전문적인 '초등학교 인공지능 질문 연구원'이야.
아이들이 작성한 질문을 분석하여 6가지 내리숲 질문 유형 중 하나로 정확하게 분류하고, 더욱 깊이 있고 성숙한 질문으로 다듬어 주어야 해.
어린이의 눈높이에 맞는 부드럽고 다정한 한국어 톤앤매너(초등학교 교사의 말투, '~해보자!', '정말 멋진걸?')를 사용해줘.

[분류 체계 기준 - 3단계 6유형]
[기초 단계 - 사실적 질문] 1. 관찰 질문: 1학년 서사. 주변 세계 관찰, 사실적 내용 및 정보 확인. 2. 공감 질문: 2학년 서사. 감정 자각, 상황을 바꾸어 가정하고 공감 (발달 순서상 기초 단계이지만, 사실적 질문에서 개념적 질문으로 넘어가는 다리 역할의 전환적 성격).
[심화 단계 - 개념적 질문] 3. 해석 질문: 3학년 서사. '왜','어떻게'를 활용해 숨은 의미와 원인 파악. 4. 표현 질문: 4학년 서사. 여러 개념을 엮거나 탐구 내용을 구조화하여 표현.
[확장 단계 - 논쟁적 질문] 5. 판단 질문: 5학년 서사. 근거를 바탕으로 가치를 비판적으로 판단하고 타당성 검토. 6. 실천 질문: 6학년 서사. 일상생활과 연결하고 실행할 수 있는 행동 모색 (정해진 답 없이 배움을 삶에 적용·전이하는 성격).

[gradeNarrative에는 반드시 다음 중 하나를 그대로 사용] 1학년 [관찰] '무엇이 보일까?' / 2학년 [공감] '어떤 느낌일까?' / 3학년 [해석] '무슨 의미일까?' / 4학년 [표현] '어떻게 말할까?' / 5학년 [판단] '타당할까?' / 6학년 [실천] '무엇을 바꿀까?'
[baseStage에는 분류에 맞게 다음 중 하나를 그대로 사용] 관찰=B (Books) - 준비하기 / 공감=B (Books) - 탐구하기 / 해석=A (Advance) - 탐구하기 / 표현=S (Share) - 정리하기 / 판단=S (Share) - 정리하기 / 실천=E (Ethics) - 실천하기

[질문 정제 규칙 - 가장 중요!]
- 목표는 '새로운 질문 만들기'가 아니라 '학생의 질문을 그대로 다듬기'야. 학생이 묻고 싶었던 것(질문의 의미와 의도)을 절대 바꾸지 마.
- 다른 방향의 질문으로 바꾸기, 이유를 되묻는 질문으로 변형하기, 주제를 넓히거나 좁혀서 다른 것을 묻기 — 모두 금지.
- 세 단계는 모두 '같은 것을 묻는 같은 질문'이어야 하고, 표현만 점점 정교해져야 해.
- 1단계 (문장 바르게): 뜻은 그대로 두고, 문장을 바르고 자연스러운 완성형 질문으로 정돈.
- 2단계 (낱말 정확하게): 뜻은 그대로 두고, 흐릿하거나 일상적인 낱말을 정확한 낱말과 교과 용어로 교체 (예: '이거' → 구체적 이름, 'AI' → '인공지능', '어떡해요' → '어떻게 대처해야 할까요').
- 3단계 (탐구 질문으로 완성): 뜻은 그대로 두고, 대상·조건·상황을 구체적으로 밝혀 수업에서 바로 탐구할 수 있는 완성형 질문으로 정제.

[정제 모범 예시]
원래 질문: "AI가 사람 해치면 어떡해요?"
- 1단계: "AI가 사람을 해치면 어떻게 해야 할까요?"
- 2단계: "인공지능이 사람에게 해를 끼친다면 우리는 어떻게 대처해야 할까요?"
- 3단계: "인공지능이 사람에게 해를 끼치는 일이 실제로 일어난다면, 그 피해를 막기 위해 우리는 어떤 대처 방법을 마련해야 할까요?"
(세 문장 모두 '해치면 어떡하나'라는 같은 물음이고, 표현만 단계적으로 정확해졌음)

[응답 형식 - 매우 중요] 반드시 아래 JSON 스키마만 응답해. 마크다운 코드블록, 인사말, 다른 텍스트를 절대 섞지 마.
{"original":"원래 질문","classification":"6유형 중 하나","explanation":"분류 이유 1~2문장","gradeNarrative":"학년 서사","baseStage":"단계","refinedOptions":[{"level":"1단계 (문장 바르게)","text":"..."},{"level":"2단계 (낱말 정확하게)","text":"..."},{"level":"3단계 (탐구 질문으로 완성)","text":"..."}],"cheerUpMessage":"응원 한 문장","forestElement":"tree|flower|sprout|leaf 중 하나"}`;

  const userQuery = `어린이가 제출한 질문: "${input}"\n선택한 학년 설정: ${gradeText}\n\n위 질문을 분석해서 여섯 가지 질문 유형 중 가장 적합한 하나를 골라 분류해줘. 그리고 학생이 묻고 싶었던 의미는 그대로 유지한 채, 이 질문 자체를 1단계(문장 바르게) → 2단계(낱말 정확하게) → 3단계(탐구 질문으로 완성) 순서로 점점 정교하게 정제해줘. 학년 수준에 맞는 낱말을 사용하고, 다정함이 묻어나는 응원 메시지도 동봉해줘. JSON만 응답해.`;

  try {
    if (!GEMINI_API_KEY) throw new Error('API 키 미설정');
    const raw = await callGemini(systemPrompt, userQuery, true);
    const clean = raw.replace(/```json|```/g, '').trim();
    state.analysisResult = JSON.parse(clean);
  } catch (e) {
    state.isFallbackActive = true;
    state.fallbackReason = GEMINI_API_KEY ? 'network' : 'no_key';
    state.analysisResult = simulateFallback(input);
  } finally {
    state.isLoading = false;
    clearInterval(loadingTimer);
    $('#btnAnalyze').disabled = false;
    $('#btnAnalyze').innerHTML = '🌱 내 질문 씨앗 심기!';
    renderLabResult();
  }
}

function simulateFallback(input) {
  let c = "해석 질문", ex = "질문에 담긴 '왜'와 '어떻게'의 요소를 분석해 열린 질문으로 탐색해 보았어요.",
      gn = "3학년 [해석] '무슨 의미일까?'", bs = "A (Advance) - 탐구하기", el = "sprout";
  if (input.includes("만약") || input.includes("느낌") || input.includes("마음")) {
    c="공감 질문"; ex="실제 상황에 나를 대입해보거나 상대방의 마음에 공감해보는 따뜻한 질문이에요.";
    gn="2학년 [공감] '어떤 느낌일까?'"; bs="B (Books) - 탐구하기"; el="flower";
  } else if (input.includes("어떻게 행동") || input.includes("실천") || input.includes("실생활") || input.includes("우리 학교")) {
    c="실천 질문"; ex="수업이나 책에서 얻은 참된 깨달음을 현실 세계의 작은 행동으로 직접 이끌어 내려는 멋진 질문이에요.";
    gn="6학년 [실천] '무엇을 바꿀까?'"; bs="E (Ethics) - 실천하기"; el="tree";
  } else if (input.includes("맞나요") || input.includes("무엇인가요") || input.includes("사실") || input.includes("이름")) {
    c="관찰 질문"; ex="책이나 사실 진술에 나타난 핵심적인 팩트와 정보를 명확하게 가리는 훌륭한 디딤돌 질문이에요.";
    gn="1학년 [관찰] '무엇이 보일까?'"; bs="B (Books) - 준비하기"; el="leaf";
  } else if (input.includes("타당") || input.includes("판단") || input.includes("옳은가") || input.includes("잘못")) {
    c="판단 질문"; ex="인물의 선택이나 특정 가치에 대해 올바른 판단을 내리고 근거를 마련해 보고자 하는 무게감 있는 질문이에요.";
    gn="5학년 [판단] '타당할까?'"; bs="S (Share) - 정리하기"; el="tree";
  }
  // 원문의 의미를 유지하며 안전하게 정제 (간이 분석기용)
  // ※ 규칙 기반이라 무리한 어미 변형은 하지 않고, 확실한 표현만 다듬어 오류를 방지
  const tidy = (t) => t.replace(/\s+/g, ' ').trim();
  const ensureQ = (t) => tidy(t).replace(/[?？!]*$/, '') + '?';

  // 1단계: 문장 바르게 — 앞뒤 공백·중복 물음표 정리, 완성형 물음표로
  const step1 = ensureQ(input);

  // 2단계: 낱말 정확하게 — 흐릿한 낱말을 정확한 낱말로 치환
  // ※ 한글 조사와 함께 오는 'AI'는 조사까지 맞춰 교정 (인공지능이/은/을 …)
  let tightened = input;
  const replaceMap = [
    [/AI가/gi, '인공지능이'], [/AI는/gi, '인공지능은'], [/AI를/gi, '인공지능을'],
    [/AI의/gi, '인공지능의'], [/AI도/gi, '인공지능도'], [/AI와/gi, '인공지능과'],
    [/AI/gi, '인공지능'],
    [/에이아이가/g, '인공지능이'], [/에이아이는/g, '인공지능은'], [/에이아이/g, '인공지능'],
    [/컴퓨터가 스스로/g, '인공지능이 스스로'],
    [/어떡해요|어떡해/g, '어떻게 해야 할까요'],
    [/뭐예요|뭐에요|뭐야/g, '무엇일까요']
  ];
  replaceMap.forEach(([re, to]) => { tightened = tightened.replace(re, to); });
  const step2 = ensureQ(tightened);

  // 3단계: 탐구 질문으로 완성 — 의미는 그대로, 탐구를 돕는 안내만 덧붙임
  const step3 = ensureQ(tightened).replace(/\?$/, '') + '? (그렇게 생각한 까닭도 함께 살펴봐요)';

  return {
    original: input, classification: c, explanation: ex, gradeNarrative: gn, baseStage: bs,
    refinedOptions: [
      { level:"1단계 (문장 바르게)", text: step1 },
      { level:"2단계 (낱말 정확하게)", text: step2 },
      { level:"3단계 (탐구 질문으로 완성)", text: step3 }
    ],
    cheerUpMessage: "지금은 숲속 간이 분석기가 규칙에 따라 문장을 다듬어 주었어요. 실시간 AI 박사님이 연결되면 훨씬 더 정교하게 정제해 줄 거예요! 🌿",
    forestElement: el
  };
}

/* ===================== 렌더링: 연구실 ===================== */
function renderLoading() {
  loadingStep = 0;
  $('#labResult').innerHTML = `
    <div class="card placeholder-box" style="border-style:solid !important;">
      <div class="loading-ring"><div class="loading-leaf">🍃</div></div>
      <div>
        <h3 style="font-size:16px; font-weight:800; color:var(--slate-900);">내리숲 AI 질문 연구원 열일 중!</h3>
        <p id="loadingMsg" class="pulse" style="font-size:13px; font-weight:700; color:var(--emerald-600); margin-top:8px;">${LOADING_MESSAGES[0]}</p>
        <p style="font-size:11.5px; color:var(--slate-400); margin-top:6px;">잠시만 기다려 주시면 반짝이는 질문 열매를 만들어 드릴게요.</p>
      </div>
    </div>`;
  clearInterval(loadingTimer);
  loadingTimer = setInterval(() => {
    loadingStep = (loadingStep + 1) % 4;
    const el = $('#loadingMsg');
    if (el) el.textContent = LOADING_MESSAGES[loadingStep];
  }, 1200);
}

function renderLabResult() {
  const r = state.analysisResult;
  if (!r) return;
  const typeEmoji = QUESTION_TYPES[r.classification]?.emoji || "🌟";
  let banner = '';
  if (state.isFallbackActive && state.fallbackReason === 'no_key') {
    // API 키가 설정되지 않은 경우: 사실 그대로 안내
    banner = `
    <div class="banner-warn">
      <div style="font-size:28px;">🔑</div>
      <div>
        <h4>지금은 '숲속 간이 분석기' 모드로 작동하고 있어요!</h4>
        <p>아직 실시간 AI 박사님과 연결되지 않아서, 지금 보시는 분석표는 앱 속에 들어있는 <strong>숲속 간이 분석기</strong>가 만든 결과입니다. 간이 분석기도 질문 유형을 나누어 주지만, 더 똑똑하고 자세한 실시간 AI 분석을 받고 싶다면 <strong>선생님께 알려 주세요!</strong></p>
        <span class="banner-tag">선생님께 🔧: 파일 상단 [선생님 전용 설정 구역]에 Gemini API 키를 넣으면 실시간 AI 분석이 켜집니다.</span>
      </div>
    </div>`;
  } else if (state.isFallbackActive) {
    // 키는 있으나 실제 접속에 실패한 경우: 혼잡/연결 안내
    banner = `
    <div class="banner-warn">
      <div style="font-size:28px;">🚦</div>
      <div>
        <h4>AI 박사님이 지금 생각의 줄을 서고 있어요! (접속 지연 안내)</h4>
        <p>많은 친구들이 동시에 질문 연구를 시작했거나 인터넷 연결이 원활하지 않아, 지금 보시는 분석표는 <strong>숲속 예비 발전기(오프라인 간이 분석)</strong>가 가동한 임시 지혜 결과입니다. 진짜 실시간 AI 박사님의 조언을 받고 싶다면, <strong>잠시 뒤에 다시 질문을 전송해 보거나 선생님께 알려 주세요!</strong></p>
        <span class="banner-tag">교실 속 대처 방법: 차례차례 가위바위보 순서대로 전송해봐요! 🙋‍♂️</span>
      </div>
    </div>`;
  }

  const refineItems = (r.refinedOptions || []).map((o, i) => `
    <div class="refine-item" data-refine="${i}">
      <div style="flex:1;">
        <span class="refine-level">${esc(o.level)}</span>
        <p class="refine-text">${esc(o.text)}</p>
      </div>
      <span class="refine-save">숲에 보관 →</span>
    </div>`).join('');

  $('#labResult').innerHTML = `
    ${banner}
    <div class="card">
      <div class="result-meta">
        <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
          <span class="pill pill-report">질문 분석 보고서</span>
          <span class="pill pill-gray">${esc(r.gradeNarrative)}</span>
        </div>
        <span style="font-size:11px; font-weight:800; color:var(--slate-400);">B.A.S.E 단계: <span style="color:var(--emerald-600);">${esc(r.baseStage)}</span></span>
      </div>
      <span style="font-size:11px; color:var(--slate-400); font-weight:800;">내가 처음 적어본 질문:</span>
      <blockquote class="result-original" style="margin-top:6px;">"${esc(r.original)}"</blockquote>
      <div class="result-verdict">
        <div class="v-emoji">${typeEmoji}</div>
        <div>
          <h3>이 질문은 <span class="highlight">${esc(r.classification)}</span>에 속해요!</h3>
          <p>${esc(r.explanation)}</p>
        </div>
      </div>
    </div>
    <div class="card" style="margin-top:18px;">
      <div style="display:flex; flex-wrap:wrap; justify-content:space-between; align-items:center; gap:8px; margin-bottom:14px;">
        <h3 style="font-size:15px; font-weight:800; color:var(--slate-900);">✨ AI 질문 정제 장치 (더 정교한 질문 다듬기)</h3>
        <span style="font-size:11px; color:var(--slate-400);">원하는 질문을 클릭하여 나의 질문 숲으로 보내세요!</span>
      </div>
      <div style="display:grid; gap:10px;">${refineItems}</div>
    </div>
    <div class="cheer-card">
      <div class="glow"></div>
      <div class="cheer-head">
        <div class="heart">💚</div>
        <div>
          <h4>질문 연구원 박사님의 한 줄 격려</h4>
          <p>내리숲초등학교 어린이의 꿈을 지지해요</p>
        </div>
      </div>
      <p class="cheer-msg">"${esc(r.cheerUpMessage)}"</p>
    </div>`;

  document.querySelectorAll('#labResult .refine-item').forEach(el => {
    el.addEventListener('click', () => {
      const idx = Number(el.dataset.refine);
      saveToForest(r.refinedOptions?.[idx]?.text);
    });
  });
}

/* ===================== 질문 숲 ===================== */
function saveToForest(refinedText) {
  const r = state.analysisResult;
  if (!r) return;
  state.savedQuestions.unshift({
    id: Date.now(),
    original: r.original,
    classification: r.classification || "해석 질문",
    refined: refinedText || r.refinedOptions?.[1]?.text || "알찬 탐구 질문",
    date: new Date().toISOString().split('T')[0],
    forestElement: r.forestElement || "sprout"
  });
  persistForest();
  updateForestCount();
  showToast("🌲 질문을 나의 질문 숲에 안전하게 보관했어요! 숲이 자라나고 있습니다.");
}

function deleteQuestion(id) {
  state.savedQuestions = state.savedQuestions.filter(q => q.id !== id);
  state.selectedForSummary = state.selectedForSummary.filter(x => x !== id);
  persistForest();
  updateForestCount();
  renderForest();
  showToast("🍂 질문을 숲에서 조심스럽게 옮겨 심었습니다.");
}

function toggleSummary(id) {
  if (state.selectedForSummary.includes(id)) {
    state.selectedForSummary = state.selectedForSummary.filter(x => x !== id);
  } else {
    if (state.selectedForSummary.length >= 3) {
      showToast("핵심 문장은 최대 3개의 질문만 선택해 연결해 주세요!");
      return;
    }
    state.selectedForSummary.push(id);
  }
  renderForest();
}

async function generateGeneralization() {
  if (state.selectedForSummary.length < 2) {
    showToast("적어도 2개 이상의 질문을 숲에서 꺼내 연결해 주세요!");
    return;
  }
  state.isSummarizing = true;
  state.generalization = '';
  renderForest();

  const selectedTexts = state.savedQuestions
    .filter(q => state.selectedForSummary.includes(q.id))
    .map(q => `[유형: ${q.classification}] ${q.refined}`);

  const systemPrompt = `너는 초등학교 학생들의 탐구를 돕는 우수한 내리숲 교육과정 설계 조력자야.
선택된 2~3개의 탐구 질문에 담긴 핵심 개념들을 유기적으로 엮어서,
학생들이 탐구의 최종 결과로 자기 언어로 간직할 수 있는 명료하고 고차원적인 '핵심 문장 (일반화 문장)'을 한 문장으로 예쁘게 도출해 주어야 해.
다른 설명이나 인사말 없이, 핵심 문장 한 문장만 응답해.`;
  const userQuery = `다음은 학생들이 탐구 과정에서 정립한 심화 질문들입니다:\n${selectedTexts.join('\n')}\n\n이 질문들을 관통하는 깊이 있는 '핵심 문장'을 30자~60자 내외로 정교하고 친근하게 작성해 주세요. 문장만 응답하세요.`;

  try {
    if (!GEMINI_API_KEY) throw new Error('API 키 미설정');
    const raw = await callGemini(systemPrompt, userQuery, false);
    if (!raw) throw new Error();
    state.generalization = raw.trim().replace(/^["']|["']$/g, '');
    showToast("✨ 지식의 꽃을 피우는 명료한 '핵심 문장'이 탄생했어요!");
  } catch (e) {
    const fb = [
      "배움과 성찰은 지식에만 머무는 것이 아니라, 우리의 도덕적인 행동과 책임으로 이어질 때 온전히 깊어집니다.",
      "인공지능과 현대 기술을 탐구할 때는 신뢰성과 책임의 기준을 세우고, 우리 일상의 행동 약속으로 완성시켜 나가야 합니다.",
      "소중한 가치를 발견하고 보전하려는 적극적인 호기심이 모여 우리의 지혜를 밝히는 등불이 됩니다."
    ];
    state.generalization = fb[Math.floor(Math.random() * fb.length)];
    showToast("💡 멋진 탐구의 씨앗들로 생각의 꽃(일반화 문장)을 피워냈어요!");
  } finally {
    state.isSummarizing = false;
    renderForest();
  }
}

function updateForestCount() {
  $('#forestCount').textContent = state.savedQuestions.length;
  $('#forestPoints').textContent = (state.savedQuestions.length * 10) + ' FP';
}

function renderForest() {
  const qs = state.savedQuestions;

  // 왼쪽 패널
  let listHtml;
  if (qs.length === 0) {
    listHtml = `<div class="empty-forest">
      <span class="leaf">🍃</span>
      <p>아직 나의 질문 숲에 심은 질문이 없어요.</p>
      <button id="goLab" style="color:var(--emerald-600); font-weight:800; font-size:12px; text-decoration:underline; margin-top:8px;">질문 연구실로 가서 첫 씨앗을 심어봐요!</button>
    </div>`;
  } else {
    listHtml = `<div class="q-list">` + qs.map(q => {
      const sel = state.selectedForSummary.includes(q.id);
      return `<div class="q-item ${sel ? 'selected' : ''}">
        <button class="q-check" data-check="${q.id}">${sel ? '✓' : ''}</button>
        <div style="flex:1;">
          <span class="q-type">${esc(q.classification)}</span><span class="q-date">${esc(q.date)}</span>
          <p class="q-refined">${esc(q.refined)}</p>
          <p class="q-original">초기 질문: "${esc(q.original)}"</p>
        </div>
        <button class="q-del" data-del="${q.id}">지우기</button>
      </div>`;
    }).join('') + `</div>`;
  }

  let genHtml = '';
  if (qs.length >= 2) {
    genHtml = `<div class="gen-box">
      <h4>🗺️ 탐구 가이드 핵심 문장(일반화) 창조기</h4>
      <p class="gen-help">질문 2~3개를 체크한 후 아래 버튼을 누르면 개념을 한데 엮은 멋진 일반화 격언이 생성됩니다.</p>
      <button class="btn-gen" id="btnGen" ${state.selectedForSummary.length < 2 || state.isSummarizing ? 'disabled' : ''}>
        ${state.isSummarizing ? '⏳ 개념 융합하는 중...' : "선택한 질문들로 '한 줄 핵심 문장' 완성하기"}
      </button>
      ${state.generalization ? `<div class="gen-result">
        <span class="gen-label">✨ 내리숲 질문중심 학습 문장</span>
        <p>"${esc(state.generalization)}"</p>
      </div>` : ''}
    </div>`;
  }

  $('#forestPanel').innerHTML = `
    <div class="forest-head">
      <div>
        <h2 style="font-size:19px; font-weight:800; color:var(--slate-900);">🌲 나의 질문 숲 정원사</h2>
        <p style="font-size:11.5px; color:var(--slate-400); margin-top:4px;">보관 중인 알찬 질문 씨앗들을 엮어 지식의 결정체인 '핵심 문장(일반화)'을 창조할 수 있습니다.</p>
      </div>
      <span class="forest-count">숲 규모: ${qs.length} 그루</span>
    </div>
    ${listHtml}${genHtml}`;

  // 오른쪽 정원
  const field = $('#gardenField');
  if (qs.length === 0) {
    field.innerHTML = `<p class="garden-empty">정원이 텅 비었습니다.<br>어서 첫 질문 씨앗을 심어 정원을 푸르게 채우고 성장시켜 보세요.</p>`;
  } else {
    field.innerHTML = qs.map(item => {
      const map = { tree:['p-tree','🌲'], flower:['p-flower','✨'], sprout:['p-sprout','🍃'], leaf:['p-leaf','🍃'] };
      const [cls, ico] = map[item.forestElement] || ['p-leaf','🍃'];
      return `<div class="plant" title="[${esc(item.classification)}] ${esc(item.refined)}">
        <div class="p-circle ${cls}">${ico}</div>
        <div class="p-stem"></div>
        <span class="p-tag">${esc((item.classification || '질문').substring(0,2))}</span>
      </div>`;
    }).join('');
  }
  updateForestCount();

  // 이벤트 바인딩
  document.querySelectorAll('#forestPanel [data-check]').forEach(el =>
    el.addEventListener('click', () => toggleSummary(Number(el.dataset.check))));
  document.querySelectorAll('#forestPanel [data-del]').forEach(el =>
    el.addEventListener('click', () => deleteQuestion(Number(el.dataset.del))));
  const goLab = $('#goLab');
  if (goLab) goLab.addEventListener('click', () => switchTab('lab'));
  const btnGen = $('#btnGen');
  if (btnGen) btnGen.addEventListener('click', generateGeneralization);
}

/* ===================== 질문 도감 ===================== */
function renderEncyclopedia() {
  const stages = [
    { tag:'1단계', title:'기초 단계 (사실적 질문)', desc:'1~2학년 [관찰/공감] 시기의 질문들로 사실을 확인하고 감정에 공감하며 질문의 기초를 다지는 단계입니다.',
      bg:'var(--blue-50)', border:'var(--blue-100)', tagBg:'var(--blue-500)', titleColor:'var(--blue-900)', descColor:'var(--blue-700)', types:['관찰 질문','공감 질문'] },
    { tag:'2단계', title:'심화 단계 (개념적 질문)', desc:'3~4학년 [해석/표현] 시기의 질문들로 의미를 찾고 구조화하는 단계입니다.',
      bg:'var(--indigo-50)', border:'var(--indigo-100)', tagBg:'var(--indigo-500)', titleColor:'var(--indigo-900)', descColor:'var(--indigo-700)', types:['해석 질문','표현 질문'] },
    { tag:'3단계', title:'확장 단계 (논쟁적 질문)', desc:'5~6학년 [판단/실천] 시기의 질문들로 비판적으로 판단하고 배움을 삶에 적용·전이하는 단계입니다.',
      bg:'var(--emerald-50)', border:'var(--emerald-100)', tagBg:'var(--emerald-500)', titleColor:'var(--emerald-800)', descColor:'var(--emerald-700)', types:['판단 질문','실천 질문'] }
  ];
  $('#encyclopediaBody').innerHTML = stages.map(s => `
    <div class="stage-head" style="background:${s.bg}; border:1px solid ${s.border};">
      <span class="stage-tag" style="background:${s.tagBg};">${s.tag}</span>
      <h3 style="color:${s.titleColor};">${s.title}</h3>
      <p style="color:${s.descColor};">${s.desc}</p>
    </div>
    <div class="type-grid">${s.types.map(renderTypeCard).join('')}</div>
  `).join('');
}
function renderTypeCard(name) {
  const info = QUESTION_TYPES[name];
  const grade = info.growthStage.split(' ')[0];
  const narrative = info.growthStage.substring(info.growthStage.indexOf(' ') + 1);
  return `<div class="type-card">
    <div class="type-body">
      <div class="type-head">
        <div class="t-title"><span style="font-size:22px;">${info.emoji}</span> ${name}</div>
        <span class="type-badge" style="background:${info.badgeColor};">${grade}</span>
      </div>
      <p class="type-desc">${info.description}</p>
      <div class="type-detail">${info.detail}</div>
      <div class="type-method">🎲 <strong>추천 질문 놀이 · ${info.method.name}</strong><br>${info.method.tip}</div>
      <span class="type-ex-label">💡 탐구 수업 예시 질문</span>
      ${info.examples.map(ex => `<div class="type-ex">• ${ex}</div>`).join('')}
    </div>
    <div class="type-foot">
      <span>🌱 성장 서사: <strong style="color:var(--slate-700);">${narrative}</strong></span>
      <span style="font-weight:800; color:var(--emerald-600);">${info.baseStage.split(' ')[0]} 단계</span>
    </div>
  </div>`;
}

/* ===================== 질문 놀이터 ===================== */
function resetQuiz(reshuffle = true) {
  if (reshuffle) state.quizSet = shuffleArray(QUIZ_BANK_BY_GRADE[state.gradeLevel]);
  state.quizIndex = 0;
  state.quizPicked = null;
  state.quizSubmitted = false;
  state.quizScore = 0;
  state.quizHint = false;
  state.streak = 0;
  state.roundCorrect = 0;
  state.lastDrop = null;
  renderQuiz();
  renderPlaygroundStats();
}

/* 탐험가 현황판 (등급 · QP · 최고 콤보 · 도감 수집률) */
function renderPlaygroundStats() {
  const kinds = ITEMS.filter(i => inv.items[i.id]).length;
  $('#playgroundStats').innerHTML = `
    <span class="stat-chip rank">${getRank(inv.points)}</span>
    <span class="stat-chip">⭐ ${inv.points} QP</span>
    <span class="stat-chip">🔥 최고 콤보 ${inv.bestStreak}</span>
    <span class="stat-chip">📖 보물 도감 ${kinds}/${ITEMS.length}종</span>`;
}

/* 보물 주머니 (수집 도감) */
function renderPouch() {
  if (!state.pouchOpen) { $('#pouchCard').style.display = 'none'; return; }
  $('#pouchCard').style.display = 'block';
  const order = { legend:0, rare:1, common:2 };
  const sorted = [...ITEMS].sort((a,b) => order[a.rarity] - order[b.rarity]);
  const total = ITEMS.length;
  const kinds = ITEMS.filter(i => inv.items[i.id]).length;
  $('#pouchCard').innerHTML = `
    <div style="display:flex; flex-wrap:wrap; justify-content:space-between; align-items:center; gap:8px; margin-bottom:14px;">
      <h3 style="font-size:15px; font-weight:800; color:var(--slate-900);">🎒 내 보물 주머니 <span style="color:var(--emerald-600);">(${kinds}/${total}종 수집)</span></h3>
      <span style="font-size:11px; color:var(--slate-400); font-weight:700;">정답을 맞힐 때마다 숲속 보물이 모여요! ❓는 아직 발견하지 못한 보물이에요.</span>
    </div>
    <div class="pouch-grid">` +
    sorted.map(it => {
      const cnt = inv.items[it.id] || 0;
      if (!cnt) return `<div class="pouch-item locked"><span class="pi-emoji">❓</span><div class="pi-name">???</div><span class="rar-tag rt-${it.rarity}">${RARITY_LABEL[it.rarity]}</span></div>`;
      return `<div class="pouch-item rar-${it.rarity}"><span class="pi-count">×${cnt}</span><span class="pi-emoji">${it.emoji}</span><div class="pi-name">${it.name}</div><span class="rar-tag rt-${it.rarity}">${RARITY_LABEL[it.rarity]}</span></div>`;
    }).join('') + `</div>`;
}

function togglePouch() {
  state.pouchOpen = !state.pouchOpen;
  $('#btnPouch').textContent = state.pouchOpen ? '🎒 보물 주머니 닫기' : '🎒 내 보물 주머니 열기';
  renderPouch();
}

function renderQuiz() {
  const q = state.quizSet[state.quizIndex];
  if (!q) return;
  const total = state.quizSet.length;
  const isLast = state.quizIndex === total - 1;

  const optsHtml = QUIZ_OPTIONS.map(opt => {
    let cls = 'quiz-opt';
    if (!state.quizSubmitted && state.quizPicked === opt) cls += ' picked';
    if (state.quizSubmitted) {
      if (opt === q.answer) cls += ' correct';
      else if (state.quizPicked === opt) cls += ' wrong';
      else cls += ' dim';
    }
    return `<button class="${cls}" data-opt="${esc(opt)}" ${state.quizSubmitted ? 'disabled' : ''}>${opt}</button>`;
  }).join('');

  // 채점 피드백 + 보물 획득 연출
  let feedback = '';
  if (state.quizSubmitted) {
    if (state.quizPicked === q.answer) {
      feedback = `<div class="quiz-feedback fb-good">🎉 정답이에요! ${state.streak >= 2 ? `🔥 ${state.streak}콤보 달성! 콤보가 쌓이면 더 귀한 보물이 나와요!` : '질문을 올바르게 통찰하는 역량을 가졌네요!'}</div>`;
      const d = state.lastDrop;
      if (d) {
        feedback += `
          <div class="item-reveal ir-${d.item.rarity}">
            <div class="ir-title">🎁 숲속 보물 발견! [${RARITY_LABEL[d.item.rarity]}]</div>
            <span class="ir-emoji">${d.item.emoji}</span>
            <div class="ir-name">${d.item.name} ${d.isNew ? '<span style="font-size:11px; color:var(--emerald-600);">✦ 도감 새 등록!</span>' : ''}</div>
            <div class="ir-sub">⭐ +${d.gained} QP 획득 · 보물 주머니에 쏙 들어갔어요</div>
            ${d.bonus ? `<div class="ir-sub" style="margin-top:8px; font-weight:800; color:#b45309;">🏆 퍼펙트 클리어 보너스! [전설] ${d.bonus.emoji} ${d.bonus.name} 추가 획득!</div>` : ''}
          </div>`;
      }
    } else {
      feedback = `<div class="quiz-feedback fb-bad">💡 아쉬워요! 정답은 <u>"${esc(q.answer)}"</u>입니다. 콤보는 처음부터 다시! 힌트를 살펴보고 다음 보물에 도전해요.</div>`;
    }
  }

  $('#quizCard').innerHTML = `
    <div class="quiz-meta">
      <span style="font-weight:800;">문제 ${state.quizIndex + 1} / ${total}</span>
      <span style="display:flex; gap:6px; align-items:center;">
        <span class="streak-chip">🔥 콤보 ${state.streak}</span>
        <span class="quiz-score">맞춘 점수: ${state.quizScore} 점</span>
      </span>
    </div>
    <div class="quiz-q"><p>"${esc(q.question)}"</p></div>
    <button class="hint-toggle" id="hintToggle">❓ ${state.quizHint ? '힌트 닫기' : '힌트 열어보기'}</button>
    ${state.quizHint ? `<div class="hint-box">${esc(q.hint)}</div>` : ''}
    <div class="quiz-options">${optsHtml}</div>
    ${feedback}
    ${!state.quizSubmitted
      ? `<button class="btn-dark" id="btnSubmitQuiz" style="margin-top:4px;">🎁 정답 확인하고 보물 열기</button>`
      : `<button class="btn-green" id="btnNextQuiz" style="margin-top:14px;">${isLast ? '🔄 새로운 순서로 다시 탐험하기' : '다음 보물 찾으러 가기 →'}</button>`}`;

  $('#hintToggle').addEventListener('click', () => { state.quizHint = !state.quizHint; renderQuiz(); });
  document.querySelectorAll('#quizCard [data-opt]').forEach(el =>
    el.addEventListener('click', () => {
      if (state.quizSubmitted) return;
      state.quizPicked = el.dataset.opt;
      renderQuiz();
    }));

  const btnS = $('#btnSubmitQuiz');
  if (btnS) btnS.addEventListener('click', () => {
    if (!state.quizPicked) { showToast("정답 후보를 선택해 주세요!"); return; }
    state.quizSubmitted = true;

    if (state.quizPicked === q.answer) {
      // 정답: 콤보 상승 → 보물 뽑기 → QP 지급
      state.quizScore++;
      state.roundCorrect++;
      state.streak++;
      if (state.streak > inv.bestStreak) inv.bestStreak = state.streak;

      let gained = 10 + (state.streak >= 3 ? 5 : 0); // 3콤보부터 보너스 QP
      const item = rollItem(state.streak);
      const isNew = !inv.items[item.id];
      inv.items[item.id] = (inv.items[item.id] || 0) + 1;

      // 라운드 전부 정답(퍼펙트) 시 전설 보물 1개 추가 지급
      let bonus = null;
      if (isLast && state.roundCorrect === total) {
        const pool = ITEMS.filter(i => i.rarity === 'legend');
        bonus = pool[Math.floor(Math.random() * pool.length)];
        inv.items[bonus.id] = (inv.items[bonus.id] || 0) + 1;
        gained += 20;
      }

      inv.points += gained;
      state.lastDrop = { item, isNew, gained, bonus };
      saveInv();
    } else {
      // 오답: 콤보 초기화 (보물 없음)
      state.streak = 0;
      state.lastDrop = null;
    }

    renderQuiz();
    renderPlaygroundStats();
    if (state.pouchOpen) renderPouch();
  });

  const btnN = $('#btnNextQuiz');
  if (btnN) btnN.addEventListener('click', () => {
    state.quizPicked = null;
    state.quizSubmitted = false;
    state.quizHint = false;
    state.lastDrop = null;
    if (isLast) { resetQuiz(true); }
    else { state.quizIndex++; renderQuiz(); }
  });
}

/* ===================== 학년 선택 (연구실·놀이터 연동) ===================== */
function setGrade(g) {
  state.gradeLevel = g;
  document.querySelectorAll('#gradeBtns .grade-btn').forEach(b => b.classList.toggle('selected', b.dataset.grade === g));
  document.querySelectorAll('#quizGradeBtns .quiz-grade-btn').forEach(b => b.classList.toggle('selected', b.dataset.grade === g));
  resetQuiz(true);
}

/* ===================== 탭 전환 ===================== */
function switchTab(name) {
  document.querySelectorAll('nav.tabs button').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  document.querySelectorAll('.tab-section').forEach(s => s.classList.toggle('active', s.id === 'tab-' + name));
  if (name === 'forest') renderForest();
  if (name === 'quiz') renderQuiz();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

/* ===================== 초기화 ===================== */
document.addEventListener('DOMContentLoaded', () => {
  // 크레딧 표기
  $('#modalCreatorName').textContent = CREATOR_NAME;
  $('#modalOrg').textContent = ORG_NAME;
  $('#footerCredit').textContent = FOOTER_CREDIT;

  // 저장된 질문 숲 · 보물 주머니 복원
  loadForest();
  loadInv();
  updateForestCount();
  renderPlaygroundStats();

  // 정적 콘텐츠 렌더
  renderEncyclopedia();
  state.quizSet = shuffleArray(QUIZ_BANK_BY_GRADE[state.gradeLevel]);
  renderQuiz();
  renderForest();

  // 이벤트: 탭
  document.querySelectorAll('nav.tabs button').forEach(b =>
    b.addEventListener('click', () => switchTab(b.dataset.tab)));
  // 이벤트: 학년 선택 (양쪽 연동)
  document.querySelectorAll('#gradeBtns .grade-btn, #quizGradeBtns .quiz-grade-btn').forEach(b =>
    b.addEventListener('click', () => setGrade(b.dataset.grade)));
  // 이벤트: 분석
  $('#btnAnalyze').addEventListener('click', analyzeQuestion);
  // 이벤트: 보물 주머니
  $('#btnPouch').addEventListener('click', togglePouch);
  // 이벤트: 학년별 대표 질문 칩 (클릭 시 질문 입력 + 해당 학년으로 자동 전환)
  document.querySelectorAll('#sampleChips .chip').forEach(c =>
    c.addEventListener('click', () => {
      $('#inputQuestion').value = c.dataset.q;
      if (c.dataset.grade) setGrade(c.dataset.grade);
    }));
  // 이벤트: 모달
  $('#btnCreator').addEventListener('click', () => $('#modalOverlay').classList.add('show'));
  $('#modalClose').addEventListener('click', () => $('#modalOverlay').classList.remove('show'));
  $('#modalCloseBtn').addEventListener('click', () => $('#modalOverlay').classList.remove('show'));
  $('#modalOverlay').addEventListener('click', (e) => { if (e.target.id === 'modalOverlay') $('#modalOverlay').classList.remove('show'); });
});
