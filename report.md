# 조회 결과 리포트

- 대상: 우선순위 1, 165건
- 실행일: 2026-07-28
- 적용 환율 (하드코딩): JPY 9.0 / USD 1,490 / EUR 1,700 / GBP 1,950
- 이상치 기준: 중앙값의 1.5배 초과 또는 0.6배 미만 제외 (판매처 3곳 이상일 때만 적용)
- 할인율 = (기준가_원화 − 현지가_원화) / 기준가_원화. 양수면 일본 현지가가 더 쌈

> **해외가는 '평균가'가 아닙니다.** Wine-Searcher가 막혀 Vivino로 대체했는데,
> Vivino 검색 응답은 와인당 판매 오퍼를 1건만 실어 줍니다(`prices` 배열 길이 1).
> 따라서 `해외가_원화` 109건은 미국 시장의
> 특정 판매처 호가 1건이며, 여러 판매처의 평균이 아닙니다. `판정근거` 열의
> `해외평균가`는 요청하신 표기를 그대로 쓴 것이고, 실제 성격은 위와 같습니다.
> 어떤 와인이 매칭됐는지는 `해외_출처` 열에 이름째로 남겼습니다.

## 소스별 분포

| 구분 | 건수 |
|---|---:|
| 국내가 확보 (와도씨) | 19 |
| 해외가로 판정 | 109 |
| 미유통추정·판정불가 | 37 |

## Wine-Searcher 접근 가능 여부

- **차단됨** — www.wine-searcher.com: HTTP 403 (PerimeterX 봇 차단, CAPTCHA 페이지)
- 우회 시도 없이 Vivino로 전환함

## 국내가 신뢰도 분포

| 신뢰도 | 건수 |
|---|---:|
| 최신 (2년 이내) | 1 |
| 낮음 (2년 이상 경과) | 18 |

## 비교대상 확인필요

자동 매칭이 다른 큐베·다른 생산자를 잡았을 가능성이 높은 건 (할인율 85% 초과 또는 현지가가 기준가의 2.5배 초과). 계산은 정상이고 비교대상만 의심됨:

| id | 검색어 | 기준가 | 할인율 | 근거 |
|---:|---|---:|---:|---|
| 4 | Selosse-Pajon Brut | 1,698,600 | 96.7% | Vivino:Jacques Selosse Brut Rosé Champagne |
| 12 | Bollinger Pinot Noir VZ 2016 | 4,291,200 | 97.9% | Vivino:Bollinger Vieilles Vignes Françaises Blanc de Noirs Brut Cha |
| 50 | Salon 2013 | 297,985 | -331.9% | Vivino:Larkmead LMV Salon 2013 |
| 55 | Salon 2006 | 62,565 | -2590.0% | Vivino:Jean-Max Roger Le Charnay Cuvée Menetou-Salon Blanc 2006 |
| 56 | Bollinger Vignes 2012 | 533,912 | -252.3% | Vivino:Bollinger La Grande Année Rosé Brut Champagne 2012 |
| 57 | Charles Heidsieck Collection Crayères Millésime 1990 | 564,710 | -285.7% | Vivino:Charles Heidsieck Brut Millésimé 1990 |
| 164 | Jérôme Prévost Extra Brut Rosé | 506,600 | -154.1% | Vivino:Jérôme Prévost La Closerie Les Béguines Extra Brut Champagne |

## 할인율 상위 30건

| # | id | 검색어 | 현지가 | 기준가 | 할인율 | 판정근거 | 신뢰도 |
|---:|---:|---|---:|---:|---:|---|---|
| 1 | 12 | Bollinger Pinot Noir VZ 2016 | 89,100 | 4,291,200 | 97.9% | 해외평균가 | - |
| 2 | 4 | Selosse-Pajon Brut | 56,400 | 1,698,600 | 96.7% | 해외평균가 | - |
| 3 | 84 | Cazé-Thibaut Brut Grand Cru | 43,600 | 217,525 | 80.0% | 해외평균가 | - |
| 4 | 44 | Krug Vintage 2006 箱付き | 485,100 | 1,980,000 | 75.5% | 국내가 | 낮음 |
| 5 | 37 | Bollinger R.D. 2007 | 336,600 | 1,230,740 | 72.7% | 해외평균가 | - |
| 6 | 135 | André Clouet Millésime 2008 | 113,800 | 399,305 | 71.5% | 해외평균가 | - |
| 7 | 41 | Bollinger R.D. 2002 | 415,800 | 1,452,750 | 71.4% | 해외평균가 | - |
| 8 | 59 | Château de Bligny Grand Rosé Brut | 23,800 | 80,445 | 70.4% | 해외평균가 | - |
| 9 | 9 | Lanson Brut Vintage 2009 | 64,400 | 187,725 | 65.7% | 해외평균가 | - |
| 10 | 58 | Château de Bligny Grande Réserve Brut | 22,800 | 62,506 | 63.5% | 해외평균가 | - |
| 11 | 34 | Rare Champagne Champagne Rosé 2008 | 292,000 | 782,235 | 62.7% | 해외평균가 | - |
| 12 | 33 | Taittinger Comtes de Champagne 2005 | 287,100 | 747,980 | 61.6% | 해외평균가 | - |
| 13 | 92 | Robert Barbichon Réserve 4 Cépages | 54,400 | 129,556 | 58.0% | 해외평균가 | - |
| 14 | 142 | Adrien Renoir Les Cépages Grand Cru Noir | 118,800 | 275,650 | 56.9% | 해외평균가 | - |
| 15 | 102 | Vincent Couche Extra Brut | 63,400 | 138,555 | 54.2% | 해외평균가 | - |
| 16 | 113 | Francis Boulard Blanc de Blancs Vieilles Vignes 2019 | 74,200 | 162,157 | 54.2% | 해외평균가 | - |
| 17 | 114 | Francis Boulard Grand Cru 2020 | 74,200 | 162,157 | 54.2% | 해외평균가 | - |
| 18 | 60 | Charles Collin Brut | 37,600 | 81,861 | 54.1% | 해외평균가 | - |
| 19 | 111 | Nicolas Maillart Rosé Grand Cru | 73,300 | 155,690 | 52.9% | 해외평균가 | - |
| 20 | 137 | Egly-Ouriet Les | 113,800 | 239,000 | 52.4% | 국내가 | 낮음 |
| 21 | 136 | De Sousa Cuvée 3A Grand Cru | 113,800 | 238,385 | 52.3% | 해외평균가 | - |
| 22 | 18 | Delamotte Blanc de Blancs 2018 | 128,700 | 260,750 | 50.6% | 해외평균가 | - |
| 23 | 38 | Philipponnat 2009 | 376,200 | 737,550 | 49.0% | 해외평균가 | - |
| 24 | 121 | Françoise Bedel | 82,200 | 158,193 | 48.0% | 해외평균가 | - |
| 25 | 53 | Salon 2007 | 1,584,000 | 3,015,760 | 47.5% | 해외평균가 | - |
| 26 | 40 | Philipponnat 2004 | 396,000 | 724,140 | 45.3% | 해외평균가 | - |
| 27 | 5 | Stradivarius Brut 2009 | 65,300 | 119,185 | 45.2% | 해외평균가 | - |
| 28 | 21 | Bollinger Grande Année 2014 木り | 188,100 | 342,500 | 45.1% | 국내가 | 낮음 |
| 29 | 70 | Ayala Blanc de Blancs 2015 | 71,300 | 126,635 | 43.7% | 해외평균가 | - |
| 30 | 112 | Chartogne-Taillet Sainte-Anne Extra Brut | 74,200 | 131,716 | 43.7% | 해외평균가 | - |
