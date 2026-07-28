#!/usr/bin/env python3
"""
Katakana -> Spanish / Portuguese (and the few German bottles the shop files
here) for the charme-du-vin スペイン・ポルトガル category.

Kept separate from the Italian lexicon rather than merged, because several
tokens legitimately mean different things in the two catalogues:

    ヴィーニャ   Vigna (IT)      vs  Viña (ES)
    カステロ     Castello (IT)   vs  Castillo (ES)
    ヴェルデーリョ Verdelho (Madeira) vs ヴェルデーニョ Verdejo (Rueda)

Merging them would silently mistranslate one category to suit the other.
The conversion machinery (whole-token match, longest-first, unconverted
tokens left alone and flagged) is shared -- see italia_lexicon.convert,
which takes the table to use.
"""

from __future__ import annotations

from italia_lexicon import convert as _convert

LEXICON: dict[str, tuple[str, str]] = {
    # ---- Spanish producers ----------------------------------------------
    "ピングス": ("Pingus", "핑구스"),
    "フロールドピングス": ("Flor de Pingus", "플로르 데 핑구스"),
    "ペスケラ": ("Pesquera", "페스케라"),
    "ファンヒル": ("Juan Gil", "후안 힐"),
    "トーレス": ("Torres", "토레스"),
    "ヴィーニャエスメラルダ": ("Viña Esmeralda", "비냐 에스메랄다"),
    "シエラカンタブリア": ("Sierra Cantabria", "시에라 칸타브리아"),
    "ヴァレンシソ": ("Valenciso", "발렌시소"),
    "クネ": ("CVNE", "쿠네"),
    "ロペスデエレディア": ("López de Heredia", "로페스 데 에레디아"),
    "トンドレア": ("Tondonia", "톤도니아"),
    "アルダンサ": ("Ardanza", "아르단사"),
    "アルベルディ": ("Alberdi", "알베르디"),
    "クロスモガドール": ("Clos Mogador", "클로스 모가도르"),
    "ネリン": ("Nelin", "넬린"),
    "ラファエルパラシオス": ("Rafael Palacios", "라파엘 팔라시오스"),
    "アスソルテス": ("As Sortes", "아스 소르테스"),
    "ロウロ": ("Louro", "로우로"),
    "チョミンエチャニス": ("Txomin Etxaniz", "초민 에차니스"),
    "ヌマンシア": ("Numanthia", "누만시아"),
    "テルメス": ("Termes", "테르메스"),
    "アルトモンカヨ": ("Alto Moncayo", "알토 몬카요"),
    "ヴェラトン": ("Veraton", "베라톤"),
    "ベンジャミンドロスチャイルド&ベガシシリア":
        ("Benjamin de Rothschild & Vega Sicilia", "뱅자맹 드 로스차일드 & 베가 시실리아"),
    "マカン": ("Macán", "마칸"),
    "フレシネ": ("Freixenet", "프레이셰넷"),
    "コルドンネグロ": ("Cordon Negro", "코르돈 네그로"),
    "ロジャーグラート": ("Roger Goulart", "로제르 굴라르트"),
    "ラヴェントス": ("Raventós", "라벤토스"),
    "ジャンレオン": ("Jean Leon", "장 레옹"),
    "エルプンティード": ("El Puntido", "엘 푼티도"),
    "アマンシオ": ("Amancio", "아만시오"),
    "ルスコ": ("Lusco", "루스코"),
    "ガレルナ": ("Galerna", "갈레르나"),
    "フェィニャネス": ("Fefiñanes", "페피냐네스"),
    "モノポール": ("Monopole", "모노폴레"),

    # ---- Portuguese producers -------------------------------------------
    "バーベイトマディラ": ("Barbeito Madeira", "바르베이토 마데이라"),
    "ドリヴェイラ": ("D'Oliveira", "돌리베이라"),
    "ブランディーズ": ("Blandy's", "블랜디스"),
    "グラハム": ("Graham's", "그레이엄스"),
    "ソアリェイロ": ("Soalheiro", "소알례이로"),
    "アランブル": ("Alambre", "알람브르"),

    # ---- German bottles filed in this category ---------------------------
    "クレメンスブッシュ": ("Clemens Busch", "클레멘스 부쉬"),
    "マリエンブルグ": ("Marienburg", "마리엔부르크"),
    "マリエンブルグローテンプファート": ("Marienburg Rothenpfad", "마리엔부르크 로텐파트"),
    "ラインガウリースリング": ("Rheingau Riesling", "라인가우 리슬링"),
    "トロッケン": ("Trocken", "트로켄"),
    "グラウブルグンダー": ("Grauburgunder", "그라우부르군더"),
    "ヴァイスブルグンダー": ("Weissburgunder", "바이스부르군더"),
    "オーセロワ": ("Auxerrois", "옥세루아"),
    "ドルンフェルダー": ("Dornfelder", "도른펠더"),

    # ---- added for the vintage-recovery pass -----------------------------
    "コーラル": ("Coral", "코랄"),
    "ヴィニャアンダンサ": ("Viña Ardanza", "비냐 아르단사"),
    "デメディナ": ("de Medina", "데 메디나"),
    "エン": ("en", "엔"),
    "マコン": ("Mâcon", "마콩"),

    # ---- regions / appellations -----------------------------------------
    "リオハ": ("Rioja", "리오하"),
    "アルタ": ("Alta", "알타"),
    "リベラデルデュエロ": ("Ribera del Duero", "리베라 델 두에로"),
    "プリオラート": ("Priorat", "프리오라트"),
    "チャコリ": ("Txakoli", "차콜리"),
    "リアスバイシャス": ("Rías Baixas", "리아스 바이샤스"),
    "コンダード": ("Condado", "콘다도"),
    "アルマンサ": ("Almansa", "알만사"),
    "マディラ": ("Madeira", "마데이라"),
    "マデラ": ("Madeira", "마데이라"),
    "セトゥバル": ("Setúbal", "세투발"),
    "ベイラ": ("Beira", "베이라"),
    "ポート": ("Port", "포트"),

    # ---- grapes ----------------------------------------------------------
    "テンプラニーリョ": ("Tempranillo", "템프라니요"),
    "ガルナッチャ": ("Garnacha", "가르나차"),
    "アルバリーニョ": ("Albariño", "알바리뇨"),
    "ヴェルデーニョ": ("Verdejo", "베르데호"),
    "ヴェルデーリョ": ("Verdelho", "베르델류"),
    "ゴデーリョ": ("Godello", "고델료"),
    "ロウレイロ": ("Loureiro", "로우레이루"),
    "マルヴァシア": ("Malvasia", "말바시아"),
    "マルヴァジア": ("Malvasia", "말바시아"),
    "モスカテル": ("Moscatel", "모스카텔"),
    "モスカテルグラウード": ("Moscatel Graúdo", "모스카텔 그라우두"),
    "ブアル": ("Bual", "부알"),
    "セルシアル": ("Sercial", "세르시알"),
    "シラー": ("Syrah", "시라"),
    "カベルネソーヴィニヨン": ("Cabernet Sauvignon", "카베르네 소비뇽"),
    "ソーヴィニヨンブラン": ("Sauvignon Blanc", "소비뇽 블랑"),
    "シャルドネ": ("Chardonnay", "샤르도네"),
    "ピノノワール": ("Pinot Noir", "피노 누아"),
    "リースリング": ("Riesling", "리슬링"),

    # ---- classification / style -----------------------------------------
    "クリアンサ": ("Crianza", "크리안사"),
    "レゼルヴァ": ("Reserva", "레세르바"),
    "レゼルバ": ("Reserva", "레세르바"),
    "リゼルヴァ": ("Reserva", "레세르바"),
    "グランレゼルヴァ": ("Gran Reserva", "그란 레세르바"),
    "ティント": ("Tinto", "틴토"),
    "ブランコ": ("Blanco", "블랑코"),
    "ロゼ": ("Rosado", "로사도"),
    "ブリュット": ("Brut", "브뤼"),
    "ブランドブラン": ("Blanc de Blancs", "블랑 드 블랑"),
    "トューニー": ("Tawny", "토니"),
    "フロール": ("Flor", "플로르"),
    "フロールド": ("Flor de", "플로르 데"),
    "メセス": ("meses", "메세스"),
    "クアトロ": ("cuatro", "콰트로"),
    "クアトロメセス": ("cuatro meses", "콰트로 메세스"),
    "フェルメンタド": ("Fermentado", "페르멘타도"),
    "バリッカ": ("Barrica", "바리카"),
    "セッコ": ("Seco", "세코"),
    "プレミアム": ("Premium", "프리미엄"),
    "ホワイト": ("White", "화이트"),

    # ---- connectives (whole-token only) ----------------------------------
    "デ": ("de", "데"),
    "デル": ("del", "델"),
    "ド": ("de", "데"),   # Flor de Pingus; the Galician "do" reading is rarer here
    "ラ": ("La", "라"),
    "エル": ("El", "엘"),
    "マス": ("Mas", "마스"),
    "ヴィーニャ": ("Viña", "비냐"),
    "カステロ": ("Castillo", "카스티요"),
    "アシエンダ": ("Hacienda", "아시엔다"),
    "レアル": ("Real", "레알"),
}


def convert(name: str) -> dict:
    return _convert(name, LEXICON)
