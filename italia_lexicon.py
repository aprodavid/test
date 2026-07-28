#!/usr/bin/env python3
"""
Katakana -> original spelling (Italian/Spanish) + Korean transcription, for
the charme-du-vin イタリア category.

Design follows the rules in the brief, which exist because transliterating
by sound produces names that do not exist and therefore never match a price
source:

  1. Single-character tokens (ラ ア ド レ ...) are never substring-replaced.
     Replacement is whole-token only, so ド inside ドメニコ is untouched.
  2. Longest keys first, and a span that has already been converted is
     never reconsidered -- this is what stopped "S.A サンザネ" becoming
     "Sans Annee Sans Annee".
  3. A token that is not in the lexicon is LEFT AS IS and flagged
     unconverted. Nothing is invented; the unconverted list is reported so
     it can be filled in.
  4. Condition markers (※旧ラベル, 箱なし, ...) are stripped into a separate
     status field instead of polluting the search term.
  6. Korean comes from the original-language pronunciation, not from
     re-transcribing the katakana.

Entries are only included where the wine is identifiable with confidence.
Coverage is deliberately incomplete -- rule 3 makes a gap visible and
harmless, whereas a guess produces a confident wrong answer.
"""

from __future__ import annotations

import re
import unicodedata

# (italian_or_spanish, korean)
LEXICON: dict[str, tuple[str, str]] = {
    # ---- producers -------------------------------------------------------
    "ガヤ": ("Gaja", "가야"),
    "アンティノリ": ("Antinori", "안티노리"),
    "エリオアルターレ": ("Elio Altare", "엘리오 알타레"),
    "エリオグラッソ": ("Elio Grasso", "엘리오 그라소"),
    "ジャコモコンテルノ": ("Giacomo Conterno", "자코모 콘테르노"),
    "アルドコンテルノ": ("Aldo Conterno", "알도 콘테르노"),
    "ネルヴィコンテルノ": ("Nervi Conterno", "네르비 콘테르노"),
    "オルネライア": ("Ornellaia", "오르넬라이아"),
    "ロベルトヴォエルッツィオ": ("Roberto Voerzio", "로베르토 보에르치오"),
    "ロベルトヴォエルツィオ": ("Roberto Voerzio", "로베르토 보에르치오"),
    "ロベルトヴォエルッツイオ": ("Roberto Voerzio", "로베르토 보에르치오"),
    "ヴォエルッツィオ": ("Voerzio", "보에르치오"),
    "ルチアーノサンドローネ": ("Luciano Sandrone", "루치아노 산드로네"),
    "ブルーノジャコーザ": ("Bruno Giacosa", "브루노 자코사"),
    "トゥアリータ": ("Tua Rita", "투아 리타"),
    "ペトローロ": ("Petrolo", "페트롤로"),
    "ビオンディサンティ": ("Biondi-Santi", "비온디 산티"),
    "カステロディアマ": ("Castello di Ama", "카스텔로 디 아마"),
    "プロデュトリデルバルバレスコ": ("Produttori del Barbaresco", "프로두토리 델 바르바레스코"),
    "スカヴィーノ": ("Paolo Scavino", "파올로 스카비노"),
    "ダルフォルノロマーノ": ("Dal Forno Romano", "달 포르노 로마노"),
    "チェルバイオーナ": ("Cerbaiona", "체르바이오나"),
    "ドメニコクレリコ": ("Domenico Clerico", "도메니코 클레리코"),
    "クレリコ": ("Clerico", "클레리코"),
    "ファンティーニ": ("Fantini", "판티니"),
    "ジェオグラフィコ": ("Geografico", "제오그라피코"),
    "バルビ": ("Barbi", "바르비"),
    "ファットリアディバルビ": ("Fattoria dei Barbi", "파토리아 데이 바르비"),
    "アルジャーノ": ("Argiano", "아르자노"),
    "フォントディ": ("Fontodi", "폰토디"),
    "ソッティマーノ": ("Sottimano", "소티마노"),
    "アゼリア": ("Azelia", "아젤리아"),
    "プルノット": ("Prunotto", "프루노토"),
    "ヴェレノージ": ("Velenosi", "벨레노시"),
    "サンマルツァーノ": ("San Marzano", "산 마르차노"),
    "カーゼバッセ": ("Case Basse", "카세 바세"),
    "ソルデラ": ("Soldera", "솔데라"),
    "マストロヤンニ": ("Mastrojanni", "마스트로얀니"),
    "ベラヴィスタ": ("Bellavista", "벨라비스타"),
    "ゾーニン": ("Zonin", "조닌"),
    "イエルマン": ("Jermann", "예르만"),
    "ミアーニ": ("Miani", "미아니"),
    "トルマレスカ": ("Tormaresca", "토르마레스카"),
    "アヴィニョネージ": ("Avignonesi", "아비뇨네시"),
    "フェルシナ": ("Fèlsina", "펠시나"),
    "フレスコバルディ": ("Frescobaldi", "프레스코발디"),
    "ビービーグラーツ": ("Bibi Graetz", "비비 그라츠"),
    "サラッコ": ("Saracco", "사라코"),
    "ブレッツア": ("Brezza", "브레차"),
    "アルテジーノ": ("Altesino", "알테시노"),
    "ヴァルディカヴァ": ("Valdicava", "발디카바"),
    "ポッジョディソット": ("Poggio di Sotto", "포조 디 소토"),
    "カサノヴァディネリ": ("Casanova di Neri", "카사노바 디 네리"),
    "ピェヴェサンタレスティトゥタ": ("Pieve Santa Restituta", "피에베 산타 레스티투타"),
    "フェウディディサングレゴリオ": ("Feudi di San Gregorio", "페우디 디 산 그레고리오"),
    "ルイジエイナウディ": ("Luigi Einaudi", "루이지 에이나우디"),
    "バルデスピノ": ("Valdespino", "발데스피노"),
    "マッキオーレ": ("Le Macchiole", "레 마키올레"),
    "トリノーロ": ("Tenuta di Trinoro", "테누타 디 트리노로"),
    "イルパラジオ": ("Il Palagio", "일 팔라조"),
    "スキアヴェンツァ": ("Schiavenza", "스키아벤차"),
    "コルナッキア": ("Cornacchia", "코르나키아"),
    "エンリコセラフィーノ": ("Enrico Serafino", "엔리코 세라피노"),
    "タメリーニ": ("Tamellini", "타멜리니"),
    "ジーニ": ("Gini", "지니"),
    "コッレステファノ": ("Colle Stefano", "콜레 스테파노"),
    "ドゥーカディサラパルータ": ("Duca di Salaparuta", "두카 디 살라파루타"),
    "カンテ": ("Kante", "칸테"),
    "ベルテッリ": ("Bertelli", "베르텔리"),
    "カパルツォ": ("Caparzo", "카파르초"),
    "アマ": ("Ama", "아마"),
    "カステロ": ("Castello", "카스텔로"),
    "テヌータ": ("Tenuta", "테누타"),
    "ファットリア": ("Fattoria", "파토리아"),
    "ポデーレ": ("Podere", "포데레"),
    "ヴィッラ": ("Villa", "빌라"),
    "フェウディ": ("Feudi", "페우디"),
    "サングレゴリオ": ("San Gregorio", "산 그레고리오"),

    # ---- appellations ----------------------------------------------------
    "バローロ": ("Barolo", "바롤로"),
    "バルバレスコ": ("Barbaresco", "바르바레스코"),
    "ブルネロディモンタルチーノ": ("Brunello di Montalcino", "브루넬로 디 몬탈치노"),
    "ブルネロディモンタルティーノ": ("Brunello di Montalcino", "브루넬로 디 몬탈치노"),
    "ブルネロモンタルチーノ": ("Brunello di Montalcino", "브루넬로 디 몬탈치노"),
    "ブルネロ": ("Brunello", "브루넬로"),
    "ロッソディモンタルチーノ": ("Rosso di Montalcino", "로소 디 몬탈치노"),
    "ロッソディモンタルティーノ": ("Rosso di Montalcino", "로소 디 몬탈치노"),
    "ディモンタルチーノ": ("di Montalcino", "디 몬탈치노"),
    "キャンティクラシコ": ("Chianti Classico", "키안티 클라시코"),
    "キャンティ": ("Chianti", "키안티"),
    "ランゲ": ("Langhe", "랑게"),
    "ランゲロッソ": ("Langhe Rosso", "랑게 로소"),
    "バルベーラダルバ": ("Barbera d'Alba", "바르베라 달바"),
    "ネッビオーロダルバ": ("Nebbiolo d'Alba", "네비올로 달바"),
    "モスカートダスティ": ("Moscato d'Asti", "모스카토 다스티"),
    "ヴァルポリチェッラ": ("Valpolicella", "발폴리첼라"),
    "アマローネデッラヴァルポリチェッラ": ("Amarone della Valpolicella", "아마로네 델라 발폴리첼라"),
    "アマローネ": ("Amarone", "아마로네"),
    "ガヴィ": ("Gavi", "가비"),
    "ソアヴェ": ("Soave", "소아베"),
    "ソワヴェ": ("Soave", "소아베"),
    "タウラージ": ("Taurasi", "타우라시"),
    "ロッソピチェーノ": ("Rosso Piceno", "로소 피체노"),
    "ボルゲリ": ("Bolgheri", "볼게리"),
    "ガッティナーラ": ("Gattinara", "가티나라"),
    "ロエロアスネイス": ("Roero Arneis", "로에로 아르네이스"),
    "フランチャコルタ": ("Franciacorta", "프란차코르타"),
    "ランブルスコ": ("Lambrusco", "람브루스코"),
    "グレゴディトゥーフォ": ("Greco di Tufo", "그레코 디 투포"),
    "ヴェルディッキオ": ("Verdicchio", "베르디키오"),
    "マテリカ": ("Matelica", "마텔리카"),
    "コッリベリチ": ("Colli Berici", "콜리 베리치"),
    "コッリセネージ": ("Colli Senesi", "콜리 세네시"),
    "フリウリ": ("Friuli", "프리울리"),
    "トスカーナ": ("Toscana", "토스카나"),
    "トスカーノ": ("Toscano", "토스카노"),
    "トスカーナロッソ": ("Toscana Rosso", "토스카나 로소"),
    "ディトスカーナ": ("di Toscana", "디 토스카나"),
    "サレント": ("Salento", "살렌토"),
    "モデナ": ("Modena", "모데나"),
    "カステルヴェトロ": ("Castelvetro", "카스텔베트로"),
    "プリミティーヴォマンドゥリア": ("Primitivo di Manduria", "프리미티보 디 만두리아"),

    # ---- grapes ----------------------------------------------------------
    "シャルドネ": ("Chardonnay", "샤르도네"),
    "ネッビオーロ": ("Nebbiolo", "네비올로"),
    "メルロー": ("Merlot", "메를로"),
    "ソーヴィニヨンブラン": ("Sauvignon Blanc", "소비뇽 블랑"),
    "ソーヴィニヨン": ("Sauvignon", "소비뇽"),
    "ピノグリージョ": ("Pinot Grigio", "피노 그리조"),
    "ピノネロ": ("Pinot Nero", "피노 네로"),
    "ネロダヴォーラ": ("Nero d'Avola", "네로 다볼라"),
    "ネロダヴォラ": ("Nero d'Avola", "네로 다볼라"),
    "ネグロアマーロ": ("Negroamaro", "네그로아마로"),
    "バルベーラ": ("Barbera", "바르베라"),
    "モンテプルチャーノ": ("Montepulciano", "몬테풀차노"),
    "ダブルッツォ": ("d'Abruzzo", "다브루초"),
    "ヴェルメンティーノ": ("Vermentino", "베르멘티노"),
    "ペコリーノ": ("Pecorino", "페코리노"),
    "プリミティーヴォ": ("Primitivo", "프리미티보"),
    "フリウラーノ": ("Friulano", "프리울라노"),
    "サンジョヴェナーレ": ("Sangiovese", "산조베제"),

    # ---- classification / style terms ------------------------------------
    "リゼルヴァ": ("Riserva", "리제르바"),
    "スペリオーレ": ("Superiore", "수페리오레"),
    "クラシコ": ("Classico", "클라시코"),
    "グランセレツィオーネ": ("Gran Selezione", "그란 셀레치오네"),
    "グランセレツォーネ": ("Gran Selezione", "그란 셀레치오네"),
    "グランセレッティオーネ": ("Gran Selezione", "그란 셀레치오네"),
    "ロッソ": ("Rosso", "로소"),
    "ビアンコ": ("Bianco", "비안코"),
    "ヴィーニャ": ("Vigna", "비냐"),
    "ヴィニェート": ("Vigneto", "비녜토"),
    "ヴィニエティ": ("Vigneti", "비녜티"),
    "レヴィーニュ": ("Le Vigne", "레 비녜"),
    "ビオロジコ": ("Biologico", "비올로지코"),
    "ビオロジック": ("Biologico", "비올로지코"),
    "アンフォラ": ("Anfora", "안포라"),
    "アパッシメント": ("Appassimento", "아파시멘토"),
    "ゴヴェルノアッルーゾ": ("Governo all'Uso Toscano", "고베르노 알루조"),
    "エディツィオーネ": ("Edizione", "에디치오네"),
    "コレツィオーネ": ("Collezione", "콜레치오네"),
    "コレッツィオーネ": ("Collezione", "콜레치오네"),
    "アニバーサリーボトル": ("Anniversary Bottle", "애니버서리 보틀"),
    "アモンティリャード": ("Amontillado", "아몬티야도"),
    "グランキュヴェ": ("Grande Cuvée", "그랑 퀴베"),
    "アルマブリュット": ("Alma Brut", "알마 브뤼"),

    # ---- cuvées / single vineyards ---------------------------------------
    "ソライア": ("Solaia", "솔라이아"),
    "ティニャネロ": ("Tignanello", "티냐넬로"),
    "グアドアルタッソ": ("Guado al Tasso", "구아도 알 타소"),
    "チェルバロデラサラ": ("Cervaro della Sala", "체르바로 델라 살라"),
    "ぺポリ": ("Pèppoli", "페폴리"),
    "ルーチェ": ("Luce", "루체"),
    "ルチェンテ": ("Lucente", "루첸테"),
    "マッセート": ("Masseto", "마세토"),
    "グイダルベルト": ("Guidalberto", "구이달베르토"),
    "レディガフィ": ("Redigaffi", "레디가피"),
    "ガラトローナ": ("Galatrona", "갈라트로나"),
    "テスタマッタ": ("Testamatta", "테스타마타"),
    "コローレ": ("Colore", "콜로레"),
    "ソレンゴ": ("Solengo", "솔렌고"),
    "カマルカンダ": ("Ca'Marcanda", "카마르칸다"),
    "プロミス": ("Promis", "프로미스"),
    "マガーリ": ("Magari", "마가리"),
    "ダグロミス": ("Dagromis", "다그로미스"),
    "シト": ("Sito", "시토"),
    "モレスコ": ("Moresco", "모레스코"),
    "コンテイザ": ("Conteisa", "콘테이자"),
    "アレステ": ("Aleste", "알레스테"),
    "カンヌビボスキス": ("Cannubi Boschis", "칸누비 보스키스"),
    "カンヌビ": ("Cannubi", "칸누비"),
    "モンフォルティーノ": ("Monfortino", "몬포르티노"),
    "フラッチャネッロ": ("Flaccianello", "플라차넬로"),
    "パトリモ": ("Patrimo", "파트리모"),
    # article arrives as its own token (レ ディフェーゼ), so it is not repeated here
    "ディフェーゼ": ("Difese", "디페세"),
    "ブラミート": ("Bramìto", "브라미토"),
    "イルブルキーノ": ("Il Bruciato", "일 브루차토"),
    "ペルラートデルボスコ": ("Perlato del Bosco", "페를라토 델 보스코"),
    "ペルラートデラボスコ": ("Perlato del Bosco", "페를라토 델 보스코"),
    "ジュストディノートリ": ("Le Cupole / Giusto di Notri", "주스토 디 노트리"),
    "カルボナイオーネ": ("Il Carbonaione", "일 카르보나이오네"),
    "フォンタローロ": ("Fontalloro", "폰탈로로"),
    "チンクアンタ": ("Cinquanta", "친콴타"),
    "アルボリーナ": ("Arborina", "아르보리나"),
    "バローロアルボリーナ": ("Barolo Arborina", "바롤로 아르보리나"),
    "デッラヌンチャータ": ("Dell'Annunziata", "델란눈치아타"),
    "デッランヌイツィアータ": ("Dell'Annunziata", "델란눈치아타"),
    "チェレクィオ": ("Cerequio", "체레퀴오"),
    "ブッシア": ("Bussia", "부시아"),
    "ロッケ": ("Rocche", "로케"),
    "ファレット": ("Falletto", "팔레토"),
    "アジリ": ("Asili", "아실리"),
    "ラバヤ": ("Rabajà", "라바야"),
    "モンヴィリエロ": ("Monvigliero", "몬빌리에로"),
    "チェレッタ": ("Cerretta", "체레타"),
    "ジネストラ": ("Ginestra", "지네스트라"),
    "パヨレ": ("Pajorè", "파요레"),
    "クッラ": ("Currà", "쿠라"),
    "マニャコスタ": ("Magnacosta", "마냐코스타"),
    "ラパリータ": ("L'Apparita", "라파리타"),
    "ヴィーニャデルフィオーレ": ("Vigna del Fiore", "비냐 델 피오레"),
    "ヴィーニャアリオネ": ("Vigna Arione", "비냐 아리오네"),
    "ピアンデッレヴィーニュ": ("Pian delle Vigne", "피안 델레 비녜"),
    "ピアンデッロリーノ": ("Pian dell'Orino", "피안 델로리노"),
    "カステルジョコンド": ("CastelGiocondo", "카스텔조콘도"),
    "サンロレンツォ": ("San Lorenzo", "산 로렌초"),
    "サンロレンツオ": ("San Lorenzo", "산 로렌초"),
    "カスッチャ": ("Vigneto La Casuccia", "비녜토 라 카수차"),
    "ヴィニェートラカスッチャ": ("Vigneto La Casuccia", "비녜토 라 카수차"),
    "ブリッコフィアスコ": ("Bricco Fiasco", "브리코 피아스코"),
    "ブリッコアンブロディオ": ("Bricco Ambrogio", "브리코 암브로조"),
    "テッレデルバローロ": ("Terre del Barolo", "테레 델 바롤로"),
    "ヴォルテ": ("Volte", "볼테"),
    "セッレ": ("Serre", "세레"),
    "レセッレ": ("Le Serre", "레 세레"),
    "ヌォーヴェ": ("Nuove", "누오베"),
    "ヌォーヴォ": ("Nuovo", "누오보"),
    "ロッシバス": ("Rossj-Bass", "로시 바스"),
    "アルテニ": ("Alteni", "알테니"),
    "ブラッシカ": ("Brassica", "브라시카"),
    "アルテニディブラッシカ": ("Alteni di Brassica", "알테니 디 브라시카"),
    "フランチャ": ("Francia", "프란차"),
    "ヴィーニャフランチャ": ("Vigna Francia", "비냐 프란차"),
    "レイ": ("Rey", "레이"),
    "ガヤエレイ": ("Gaia & Rey", "가이아 에 레이"),
    "スリードリーマーズ": ("Three Dreamers", "스리 드리머스"),
    "メッセージインナボトル": ("Message in a Bottle", "메시지 인 어 보틀"),
    "ソリティルディン": ("Solitudine", "솔리투디네"),
    "サマス": ("Samas", "사마스"),
    "テルツェット": ("Terzetto", "테르체토"),
    "トリオーネ": ("Torrione", "토리오네"),
    "メッソリオ": ("Messorio", "메소리오"),
    "パッソデッレムーレ": ("Passo delle Mule", "파소 델레 물레"),
    "モンテブオーニ": ("Montebuoni", "몬테부오니"),
    "ボッジナ": ("Boggina", "보지나"),
    "ヴィスタマーレ": ("Vistamare", "비스타마레"),
    "オベリスコ": ("Obelisco", "오벨리스코"),
    "レニーナ": ("Renina", "레니나"),
    "ソリエラ": ("Solera", "솔레라"),

    # ---- added after reviewing the unconverted list ---------------------
    "ドメニコ": ("Domenico", "도메니코"),
    "モンフォルテ": ("Monforte", "몬포르테"),
    "ピエーヴェ": ("Pieve", "피에베"),
    "ボスコ": ("Bosco", "보스코"),
    "ペルラート": ("Perlato", "페를라토"),
    "グレゴリオ": ("Gregorio", "그레고리오"),
    "タスカ": ("Tasca d'Almerita", "타스카 달메리타"),
    "シグナス": ("Cygnus", "치뉴스"),
    "トレ": ("Tre", "트레"),
    "チンクエ": ("Cinque", "친퀘"),
    "アウトークトニ": ("Autoctoni", "아우토크토니"),
    "アントニオフェラーリ": ("Antonio Ferrari", "안토니오 페라리"),
    "モンテヴェルジネ": ("Montevergine", "몬테베르지네"),
    "ディサンフランチェスコ": ("di San Francesco", "디 산 프란체스코"),
    "トゥルッリ": ("Trulli", "트룰리"),
    "ドゥエトゥルッリ": ("Due Trulli", "두에 트룰리"),
    "グラスバロッサ": ("Grasparossa", "그라스파로사"),
    "ブレッチャローロ": ("Brecciarolo", "브레차롤로"),
    "ロッジョ": ("Roggio", "로조"),
    "フィラーレ": ("Filare", "필라레"),
    "カーザデフラ": ("Casa Defrà", "카사 데프라"),
    "カーサデフラ": ("Casa Defrà", "카사 데프라"),
    "マエストロ": ("Maestro", "마에스트로"),
    "ラロ": ("Raro", "라로"),
    "ラディーチ": ("Radici", "라디치"),

    # ---- corrections from the grade-D audit ------------------------------
    "カステロディ": ("Castello di", "카스텔로 디"),
    "カラレンタ": ("Calalenta", "칼라렌타"),
    "デルコムーネディモッラ": ("del Comune di La Morra", "델 코무네 디 라 모라"),
    "デルコムーネ": ("del Comune", "델 코무네"),
    "ディモッラ": ("di La Morra", "디 라 모라"),
    "バルベーラダルバヴィーニャ": ("Barbera d'Alba Vigna", "바르베라 달바 비냐"),
    "バルベーラダルバヴィーニャフラ": ("Barbera d'Alba Vigna Francia", "바르베라 달바 비냐 프란차"),
    "バローネ": ("Barone", "바로네"),
    "ワー": ("Were", "웨어"),
    "ドリームス": ("Dreams", "드림스"),
    "ジャローネ": ("Giarone", "자로네"),
    "ブラック": ("Black", "블랙"),
    "アルポッジョ": ("Al Poggio", "알 포조"),
    "ポッジョ": ("Poggio", "포조"),
    "ラカーサ": ("La Casa", "라 카사"),

    # ---- connectives (whole-token only; never substring-replaced) --------
    "ディ": ("di", "디"),
    "デル": ("del", "델"),
    "デッラ": ("della", "델라"),
    "デラ": ("della", "델라"),
    "デイ": ("dei", "데이"),
    "ダルバ": ("d'Alba", "달바"),
    "ダスティ": ("d'Asti", "다스티"),
    "エ": ("e", "에"),
    "ラ": ("La", "라"),
    "レ": ("Le", "레"),
    "イル": ("Il", "일"),
    "ル": ("Le", "레"),
    "サン": ("San", "산"),
    "ド": ("de", "드"),
}

# Condition / packaging markers -> 상태 column, removed from the search term.
CONDITION_MARKERS = [
    "※旧ラベル", "旧ラベル", "箱付き", "箱なし", "箱無し", "ラベル不良",
    "ビンキズ", "液面低下", "ラベル汚れ", "キャップシール不良", "アウトレット",
    "訳あり", "限定", "再入荷",
]

VOLUME_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(ml|ML|mL|L|l)\b")
_KATAKANA_RE = re.compile(r"[ァ-ヿ]")


def normalise(name: str) -> str:
    return unicodedata.normalize("NFKC", name).strip()


def split_condition(name: str) -> tuple[str, str]:
    """Rule 4: pull packaging/condition notes out of the search term."""
    found = []
    out = name
    for marker in sorted(CONDITION_MARKERS, key=len, reverse=True):
        if marker in out:
            found.append(marker)
            out = out.replace(marker, " ")
    return re.sub(r"\s+", " ", out).strip(), " ".join(found)


def extract_volume(name: str) -> tuple[str, str]:
    """Return (name without the volume token, volume string)."""
    m = VOLUME_RE.search(name)
    if not m:
        return name, "750ml"
    amount, unit = m.group(1), m.group(2).lower()
    vol = f"{amount}L" if unit == "l" else f"{int(float(amount))}ml"
    return VOLUME_RE.sub(" ", name).strip(), vol


_VINTAGE_4 = re.compile(r"\b(19[5-9]\d|20[0-3]\d)\b")
_VINTAGE_2 = re.compile(r"(?<![\d])([0-2]\d)(?![\d])")


def extract_vintage(name: str) -> tuple[str, str]:
    """Trailing 2- or 4-digit year. 2-digit years are expanded (10 -> 2010)."""
    m = _VINTAGE_4.search(name)
    if m:
        return _VINTAGE_4.sub(" ", name).strip(), m.group(1)
    m = _VINTAGE_2.search(name)
    if m:
        yy = int(m.group(1))
        return _VINTAGE_2.sub(" ", name, count=1).strip(), str(2000 + yy)
    return name, ""


def convert(name: str) -> dict:
    """Katakana product name -> structured, searchable fields.

    Tokens are matched whole and longest-first, and each token is converted
    at most once, so no span can be double-translated.
    """
    text = normalise(name)
    text, condition = split_condition(text)
    text, volume = extract_volume(text)
    text, vintage = extract_vintage(text)

    tokens = [t for t in re.split(r"[\s　・,、/（）()]+", text) if t]
    it_parts: list[str] = []
    ko_parts: list[str] = []
    unconverted: list[str] = []

    for tok in tokens:
        hit = LEXICON.get(tok)
        if hit:
            it_parts.append(hit[0])
            ko_parts.append(hit[1])
            continue
        if _KATAKANA_RE.search(tok):
            # Rule 3: never invent a romanisation.
            unconverted.append(tok)
            it_parts.append(tok)
            ko_parts.append(tok)
        else:
            it_parts.append(tok)   # already latin (e.g. IGT, VOS)
            ko_parts.append(tok)

    return {
        "original": it_parts and " ".join(it_parts) or "",
        "korean": " ".join(ko_parts),
        "vintage": vintage,
        "volume": volume,
        "condition": condition,
        "unconverted": unconverted,
        "has_unconverted": bool(unconverted),
    }


def producer_of(converted: str) -> str:
    """First non-article token of the converted name, used as the gate."""
    for tok in converted.split():
        if tok.lower() not in {"il", "la", "le", "di", "del", "della", "dei",
                               "e", "san", "de", "tenuta", "fattoria", "castello",
                               "podere", "villa", "feudi"}:
            return tok
    return converted.split()[0] if converted.split() else ""
