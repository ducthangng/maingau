# MAINGAU: tài liệu tổng thể idea, chọn hướng theo dữ liệu và kế hoạch triển khai

Phiên bản 1.0 · Chuẩn bị ngày 25/10/2026 cho deep dive 26/10/2026 · Đội 5 người · AI hỗ trợ code · Pitch tiếng Anh.

**Mục đích:** ngày mai, sau khi thấy data và nghe partner, đội có thể chọn một hướng, chốt phạm vi và chia việc ngay từ file này. Đây là thiết kế dự kiến, chưa phải mô tả sản phẩm đã build hoặc kết quả đã đo.

**Quyết định hiện tại:** ưu tiên có điều kiện **JourneyPilot — Next Feasible Offer**. Dùng **MomentPilot làm lõi quyết định** và **DecisionLab làm tính năng “Challenge this decision”**. Chuyển sang FlexMoment hoặc BillShield khi dữ liệu, pain và quyền hành động thực sự phù hợp. Chỉ build **một sản phẩm chính**, không chia năm người để làm đồng thời bốn app.

Tài liệu này tiếp thu bản review người dùng gửi ngày 25/10 và hợp nhất các memo/blueprint trong thư mục. Khi khuyến nghị cũ khác file này, dùng thứ tự: **thông tin mới trực tiếp từ ban tổ chức/partner → nguồn/policy được xác nhận đúng phạm vi → tài liệu này → bản thiết kế cũ**. Không dùng điểm 68/100, 87/100 hoặc bảng xếp hạng AI như điểm jury.

## 0. Trang quyết định nhanh cho ngày mai

### 0.1 Đề bài phải giữ đủ

> “You'll build an AI-powered tool that finds the best next offer for every single customer and delivers it through the right channel in the right tone.”

Mỗi hướng được chọn phải có ít nhất một nhánh chạy trọn:

```text
Một khách + nhu cầu + catalog/policy có nguồn
→ offer cụ thể hoặc lý do chưa thể đề xuất
→ channel được phép + timing + tone
→ message có căn cứ → review → handoff/export lưu được.
```

Không để toàn bộ demo kết thúc bằng “cần hỏi thêm”, “không liên hệ” hoặc một timeline chưa có offer. Khi không đủ điều kiện gửi, vẫn giữ hành vi chặn đúng; cần chọn thêm một ca hợp lệ để chứng minh lời giải đầy đủ.

### 0.2 Chọn theo hard gates, không chấm điểm giả chính xác

| Dữ liệu và nhu cầu được xác nhận | Hướng chọn | Phần phải chứng minh |
|---|---|---|
| Pain là phối hợp chuyển nhà/xuyên sản phẩm; có hợp đồng, action templates, điều kiện availability/lead time dùng được | **JourneyPilot** | Một thay đổi làm invalid offer/bước phụ thuộc; tính lại plan và message đúng |
| Có incentive catalog/window, customer flexibility, cơ chế tài trợ; partner chấp nhận incentive là “offer” | **FlexMoment** | Hai khách khác deadline nhận quyết định khác; budget/window chặn đúng |
| Billing surprise/proactive care là ưu tiên; có readings, tariff, payments cùng kỳ; partner chấp nhận service action và offer liên quan | **BillShield** | Dữ kiện hóa đơn dẫn tới action đúng; payment adjustment không bị gọi là giảm chi phí điện |
| Chỉ có customer snapshot, holdings/benefits, catalog, permission; không đủ dữ liệu cho ba hướng trên | **MomentPilot** | Tính benefit mới đúng, không bán lại lợi ích đã có; offer/channel/tone đầy đủ |
| Chủ yếu có campaign logs và outcomes | Chọn một use case ở trên có thể tái hiện; thêm **Historical/Evidence Mode** nếu đủ điều kiện | Không mặc định phải train uplift; kiểm assignment, action support, exposure và outcome trước |
| Chỉ có PDF, mô tả và vài ví dụ | Một case hẹp có policy/fixtures gắn nhãn; thường MomentPilot hoặc JourneyPilot giới hạn | Chứng minh cơ chế; nói rõ phần synthetic và những gì chưa kiểm được trên MAINGAU |

**Nếu nhiều hướng cùng qua gate:** ưu tiên pain partner xác nhận, rồi case có thể hoàn tất hôm nay, rồi khả năng thể hiện khác biệt trong demo. JourneyPilot là mặc định cân bằng; FlexMoment chỉ vượt lên khi đường dữ liệu và thương mại rõ. Không giữ JourneyPilot chỉ vì đã thích tên.

### 0.3 Kết quả cần chốt trước 13:00 thứ Hai

```text
Hướng duy nhất: _____________________  Người xác nhận pain: ___________________
User/decision owner: ________________  Pain hiện tại, một ví dụ: ______________
Input dùng được: ___________________  Catalog/action được phép: ______________
Current workflow/baseline: __________  Điều hiện chưa được giải quyết: _________
Một acceptance có thể quan sát: ______________________________________________
Dữ liệu được đưa tới model nào: _____  Phạm vi chỉ export / integration: _______
Pitch duration/rubric: ______________  Một offer hợp lệ trong demo: ____________
Nếu gate trượt, chuyển sang: ________  Deadline dừng tranh luận: _______________
```

## 1. Bối cảnh, bằng chứng và điều chưa biết

### 1.1 Ràng buộc thời gian

Theo email: 26/10 check-in 09:30, kickoff 10:00, deep dives 12:00; 27/10 pitch từ 15:00. Khoảng từ deep dive tới pitch là **27 giờ lịch**, còn gồm ăn, nghỉ và luyện pitch. “32 giờ” là mô tả sự kiện, không phải ngân sách 32 giờ coding trước pitch. Điều chỉnh khi ban tổ chức thông báo lịch cuối cùng.

Đội 5 người; AI giúp code các module sau khi schema/semantics được chốt. Không mặc định được dùng code chuẩn bị sẵn; xác nhận quy định tại sự kiện. Venue chỉ cho vào lại trước 00:00 và từ 06:30, trừ khi đồng đội ở trong mở cửa.

### 1.2 Nghiên cứu nói được gì?

| Dữ kiện có nguồn | Hệ quả thiết kế | Chưa chứng minh được |
|---|---|---|
| MAINGAU có sản phẩm energy, internet/mobile và e-mobility; case study Parloa mô tả tariff advice, gửi offer, meter readings, installment adjustment và connector Kraken/LIMA | Không làm thêm voice bot hoặc “AI viết email” làm lõi | Chức năng nào đang bật cho data được cấp; workflow nào còn thiếu |
| MAINGAU có hướng dẫn chuyển nhà; internet cần kiểm availability tại địa chỉ mới | Journey có constraint thực để thể hiện | Lead time/fee hiện hành của từng offer hoặc quyền chuyển một hợp đồng cụ thể |
| MAINGAU tham gia Grids & Benefits, có use case incentive cho charging | FlexMoment có liên quan miền kinh doanh | Incentive/funding/data của dự án đó có được dùng trong challenge hay không |
| FAQ/Vorteilswelt mô tả quyền lợi và việc liên kết hợp đồng/customer numbers | Tách holding, eligibility và activation | Tỷ lệ khách bỏ sót benefit hoặc MAINGAU chưa tự động xử lý |
| Pega/Kraken đã có customer journeys và decision/workflow tooling | Journey, constraints và no-contact riêng lẻ không mới | MAINGAU hiện thiếu đúng lớp orchestration nào |

Nguồn cạnh các dữ kiện: [Parloa MAINGAU](https://www.parloa.com/customers/maingau/), [MAINGAU chuyển nhà](https://www.maingau-energie.de/blog/umzug), [Grids & Benefits](https://www.unternehmertum.de/landingpages/grids-and-benefits), [Vorteilswelt](https://www.maingau-energie.de/maingau-vorteilswelt), [Pega customer journeys](https://academy.pega.com/module/defining-and-creating-customer-journeys/v1), [Kraken configuration](https://www.kraken.tech/ja/kraken-configuration). Mô tả vendor là nguồn về capability đã công bố, không phải kiểm toán độc lập hay bằng chứng ROI của đề xuất này.

**Không thể bảo đảm ít trùng đội khác hoặc thắng giải.** Tạo khác biệt bằng một tình huống đặc thù, constraint có thật, quyết định thay đổi kiểm tra được và một kết quả bàn giao hữu ích. Không dựa vào số lượng agent hoặc tên thuật toán.

### 1.3 Nhãn bắt buộc

- `PARTNER`: dữ liệu partner cấp, chỉ dùng trong phạm vi được cho phép.
- `PUBLIC_SOURCE`: nguồn công khai; vẫn kiểm phiên bản và applicability.
- `SYNTHETIC`: fixture do đội tạo, không phải tariff/data MAINGAU.
- `CONFIRMED / PROPOSED / UNKNOWN / CONFLICTING`: trạng thái tri thức/policy/fact, tách với nguồn dữ liệu.
- `LIVE / CACHED / FIXTURE`: nguồn kết quả adapter. Không gộp tất cả thành một nhãn “verified”.
- `PROJECTED`: phép tính dựa trên giả định tương lai; không phải saving guarantee hoặc measured impact.

Nếu data thật trộn với policy demo, gắn nhãn ở từng trường/quy tắc quyết định; không gọi toàn card là validated on partner data.

## 2. Data intake trong giờ đầu

### 2.1 Kiểm dữ liệu trước khi chọn câu chuyện

Trong 30–45 phút, B và A mở một sample nhỏ được phép dùng, kiểm data dictionary và dựng một case normalize. Không tải toàn bộ hồ sơ hạn chế quyền vào coding assistant chỉ vì có token miễn phí.

| Nhóm dữ liệu | Những gì cần kiểm | Cách xử lý nếu thiếu |
|---|---|---|
| Identity | customer/account/contract/service-location IDs; quyền và cơ sở liên kết | Không merge theo tên/email hoặc địa chỉ gần giống; giữ UNKNOWN |
| Catalog | offer ID/version, product family, price phases, fees, duration, exclusions, availability scope | Dùng catalog hẹp được xác nhận; chưa rõ thì PROPOSED, không ready handoff |
| Holdings/benefits | hợp đồng đang có, thời hạn, discount active/eligible/not active, stacking/caps | Không coi “đang là khách energy” là đã hưởng mọi benefit |
| Permission | purpose, channel, product scope, status, objection, timestamps/revision | Unknown chặn marketing handoff; service/requested advice có policy riêng |
| Journey | goal, move date, required-by date, address, coverage result, lead time, dependencies | Chỉ Journey khi có thể biểu diễn ít nhất một constraint thật hoặc fixture được thừa nhận |
| Flex | connector/location, window, power/energy units, customer availability/deadline, reward/caps, budget, sponsor | Thiếu funding/catalog/window thì không chọn làm sản phẩm chính |
| Bill | reading value/unit/time, actual/estimated quality, meter reset/change, tariff phases, payments đúng kỳ | Không forecast hay annualize khi chưa có baseline đáng tin |
| Outcomes | assigned action, exposure, outcome date, follow-up, control/assignment method, support | Logs mua hàng đơn thuần không là causal evidence |

### 2.2 Bốn chế độ bằng chứng

| Mode | Điều được làm | Điều không được tự nói |
|---|---|---|
| Demo policy | Chạy mechanics trên fixture có source label | Policy/tariff live, uplift, ROI thật |
| Partner snapshot / Launch | Chọn theo policy, feasibility và giá trị tính được | Đã biết tác động của offer lên người nhận |
| Historical analysis | Data diagnostics, replay, association, coverage | Có control là tự động nhân quả; mọi action đều có support |
| Experiment-backed | Estimate trong population/action/horizon có thiết kế và outcome phù hợp | Tác động cá nhân chắc chắn hoặc extrapolation sang channel/tone chưa thử |

Mode là thuộc tính bằng chứng, không phải một idea thứ năm. Trong hackathon không bắt buộc train model mới nếu không giúp acceptance của case đã chọn.

## 3. Lõi dùng chung: MomentPilot bên dưới sản phẩm được chọn

### 3.1 Decision tuple

```text
action + offer/version + allowed channel + timing + tone
       + readiness + next step + value/constraint evidence + alternative.
```

Actions: `OFFER`, `ACTIVATE_EXISTING_BENEFIT`, `REQUEST_INFORMATION`, `SERVICE_HANDOFF`, `WAIT`, `NO_MARKETING`. Với Flex, `OFFER` trỏ incentive đã duyệt. Với BillShield, service task và offer vẫn là hai action khác nghĩa, không gọi mọi nhắc hóa đơn là bán hàng.

`NO_MARKETING` không có nghĩa dừng dịch vụ khách có quyền nhận. `REQUEST_INFORMATION` không tự cho phép chủ động nhắn khách; có thể chỉ là task cho agent xác minh trong ngữ cảnh hợp lệ.

### 3.2 Pipeline tất định

1. Kiểm schema, identity scope, dữ liệu được phép dùng và policy/catalog release.
2. Xác định goal/event từ fact đã xác nhận; không tự suy ra move/churn/financial distress từ một dấu hiệu mơ hồ.
3. Tạo candidates từ menu có phiên bản, giữ alternatives hợp lý và no-marketing.
4. Kiểm eligibility/feasibility theo ba giá trị `TRUE / FALSE / UNKNOWN`. Unknown không được thành pass hoặc fail giả.
5. Tính cost/benefit trong phạm vi input; thiếu con số quan trọng thì null hoặc scenario bounds có nhãn.
6. Xếp các candidate khả thi theo customer objective và commercial policy được chốt; unknown không biến thành điểm trung bình tự bịa.
7. Chọn purpose/channel/timing theo permission và preference; chọn tone theo brand guideline/ngữ cảnh.
8. Tạo message từ typed claims, review, kiểm dependency mới nhất rồi export.

`best` chỉ nghĩa tốt nhất **trong catalog, scope, horizon, facts và policy đã công bố**. Không phải best toàn thị trường hoặc dự báo tối ưu giá trị vòng đời.

### 3.3 Ba trạng thái chi phí của khách

```text
Observed: đang thực trả và đang active benefit nào.
Entitled: có thể nhận benefit gì từ hợp đồng hiện có nếu hoàn thành điều kiện.
After-offer: mua/chuyển theo offer mới thì chi phí/quyền lợi thay đổi gì.

Net customer cost reduction(a, H)
  = total cost(reference state, H) - total cost(after action a, H).
```

So cùng horizon, đơn vị, thuế, usage assumptions và phạm vi dịch vụ. Cost gồm phí cố định, usage, phí một lần, overlap hợp đồng, discount theo phase và cap. Không kéo giá promo qua expiry. Nếu khác chất lượng dịch vụ, nói trade-off, không tự gọi chênh lệch là savings của cùng dịch vụ.

Không ghi công cho offer mới một benefit đã active hoặc có thể mở không cần mua. Mỗi dòng benefit có khóa rule version + target contract + eligible period/usage bucket; stacking phải theo terms. Margin MAINGAU, saving của khách và chi phí incentive là các đại lượng khác nhau.

### 3.4 Ranking không cần giả causal model

Mặc định: lọc hard constraints → đáp ứng mục tiêu khách đã khai báo → so trade-off trên metric có nghĩa → áp priority/tie-break được partner xác nhận. Nếu thiếu margin, commercial value để `UNKNOWN`; vẫn có thể demo lựa chọn theo mục tiêu khách nếu partner chấp nhận phạm vi đó.

Không cộng euro với utility points, không coi propensity là uplift, không dùng một “trust score” tự đặt để làm mọi action trông có lãi. Batch optimizer chỉ là P1 khi capacity/budget thật sự quan trọng và core đã chạy.

## 4. Hướng A — JourneyPilot: Next Feasible Offer

### 4.1 Ý tưởng và điều kiện chọn

> **“JourneyPilot turns a customer's goal into the next feasible offer—and updates the plan when reality changes.”**

User chính: Universal Agent hoặc CRM specialist giải quyết một nhu cầu xuyên sản phẩm. Mặc định một event **chuyển nhà**, tối đa **energy + internet**. Không mở rộng thêm mobile, shop, EV cùng lúc.

Pain giả thuyết: “phù hợp sản phẩm” chưa có nghĩa offer thực hiện được đúng nơi/đúng lúc. Cần biết điều kiện nào thiếu, bước nào phải làm trước và điều gì phải rút lại khi một fact đổi. MAINGAU đã có service chuyển nhà; phần chưa được workflow hiện tại giải quyết phải được mentor chỉ ra.

**Go:** có một case, menu action/offer, ít nhất một dependency/availability/date rule và partner chấp nhận multi-step preparation là phù hợp challenge. **No-go:** chỉ thêm timeline cho bot đã có; không có offer cụ thể; không có source cho constraint; current workflow đã giải quyết toàn bộ case.

### 4.2 Dữ liệu tối thiểu

`goal`, `move_date`, `need_service_by`, `old/new_service_location`, contracts/expiry, customer priorities, availability theo address/product và thời điểm kiểm, earliest supported date/lead-time policy, offer versions/costs, permission/preference.

Tách **ngày hỗ trợ theo dữ liệu hiện có**, **ngày yêu cầu**, **ngày nhà cung cấp xác nhận**. Không đổi một phép tính lead time thành installation booking hoặc lời hứa không gián đoạn.

### 4.3 Bounded planner

Chỉ cần 4–6 action templates; mỗi template có `requires`, `produces_fact_types`, dependency IDs, duration/date rule, owner, offer refs, source/policy version. Ví dụ:

| Template | Yêu cầu | Kết quả có thể thu được | Quy tắc |
|---|---|---|---|
| Confirm move details | Case và quyền dùng dữ liệu | Address/date/goal được xác nhận | Mơ hồ thì chưa hoàn tất |
| Check existing contracts | Contract IDs và scope | Transferability, expiry, fees | Không tự suy quyền hủy/chuyển |
| Check address availability | Address đã xác nhận | Availability có timestamp/source | `UNKNOWN` không là available |
| Compare feasible offers | Điều kiện location/date/cost đủ | Ranked candidates/trade-offs | Chỉ so candidates qua hard gates |
| Prepare energy transition | Energy facts và action policy | Task/offer/handoff phù hợp | Có thể song song với internet nếu không phụ thuộc |
| Prepare reviewed handoff | Offer/card/message và permission mới nhất | Export packet | Không tự ký/chuyển hợp đồng |

Planner có thể là DAG + topological traversal và liệt kê vài nhánh hữu hạn. Không cần autonomous agent, tìm kiếm vô hạn hoặc solver tổng quát. Reject cycle; kiểm deadline và required facts; chỉ đánh dấu step hoàn tất khi có evidence/response thật hoặc fixture được gắn nhãn.

**Một planned step tạo ra fact trong tương lai không có nghĩa fact đó đã biết.** `CHECK_AVAILABILITY` trong plan không được tự làm `available=true` chỉ vì bước này tồn tại.

### 4.4 Hỏi gì tiếp?

Từ các missing facts có thể hỏi, ưu tiên fact làm đổi feasibility hoặc thứ tự candidate: ngày cần internet, địa chỉ mới, trạng thái hợp đồng. Chọn theo dependency/boundary được định nghĩa; có thể duyệt các giá trị hữu hạn liên quan. Không tuyên bố optimal value-of-information.

Một câu trả lời có thể vẫn còn nhiều outcomes; UI giữ `possible_outcomes[]` và bước kế tiếp. Bất định từ policy phải chuyển reviewer, không hỏi khách một fact không giải quyết được policy. Nếu mọi completion đều làm một offer không khả thi thì loại/giữ blocked, không hỏi để cố cứu offer.

### 4.5 Re-planning thật

```text
Fact / offer / permission revision thay đổi
→ tìm steps, candidates, claims phụ thuộc
→ vô hiệu hóa artifact cũ để dùng tiếp, vẫn giữ lịch sử
→ đánh giá lại feasibility + ranking
→ plan/decision revision mới + message mới
→ review/preflight lại trước export.
```

Giữ các step/evidence độc lập còn đúng. Nếu chưa xây invalidation chọn lọc, có thể tính lại toàn case với cùng kết quả đúng, nhưng phải nói đó là full re-evaluation; không pitch đã tối ưu selective re-planning.

### 4.6 Bộ demo Journey

Các giá, ngày và constraint dưới là **fixture thiết kế**, phải thay bằng data/policy partner hoặc giữ nhãn synthetic. Ngày dùng timezone Europe/Berlin.

| Case | Đầu vào/thay đổi | Hành vi phải thấy |
|---|---|---|
| J1 — Unknown → concrete offer | Chuyển 15/11, cần internet 16/11, availability chưa biết; sau đó nhập kết quả xác nhận có DSL từ 15/11 | Ban đầu hỏi/check; sau xác nhận có offer cụ thể, channel/tone và packet |
| J2 — Date changes | Earliest supported date 15/11; khách đổi required-by sang 10/11 | Offer internet đó blocked về timing; không hứa ngày sớm hơn; energy độc lập vẫn được kiểm riêng |
| J3 — Availability changes | Offer fiber từng khả thi; kết quả mới fiber unavailable, DSL có thể khả thi theo catalog | Card fiber STALE; DSL chỉ được chọn nếu cũng qua date/cost/contract gates; message fiber cũ bị chặn |
| J4 — Permission changes | Email marketing rút lại sau review | Không handoff email card cũ; không tự đổi sang push/call để né objection |
| J5 — No alternate | Không có candidate đạt ngày/địa chỉ | WAIT/REQUEST_INFORMATION/SERVICE_HANDOFF đúng scope, không tự phát minh hotspot/discount |

J1 cần đi tới một offer thật trong phạm vi fixture/data, tránh demo chỉ hỏi thêm. J2/J3 là hai màn chứng minh khác biệt; J4 là kiểm an toàn, có thể để Q&A.

### 4.7 Scope và acceptance

**P0:** một journey 3–5 bước, tối đa hai families, 2–3 candidates, một câu hỏi, một offer hợp lệ, re-plan date và availability, channel/tone, persistence/replay/export. **P1:** so trade-off 2–3 phương án; selective invalidation; Challenge this decision. **Cắt:** planner tổng quát, mọi life event, giao diện timeline cầu kỳ, batch optimizer.

Đạt khi mentor thay một constraint và engine đổi đúng offer/readiness/bước phụ thuộc; message cũ không thể export như còn hiệu lực; refresh giữ lịch sử. Chưa được nói đã giảm churn, tự đổi mọi hợp đồng hoặc bảo đảm installation date.

## 5. Hướng B — FlexMoment: incentive khách thực sự có thể đáp ứng

### 5.1 Ý tưởng và ba gate

> **“The next best offer can be a reward for flexibility the customer can actually provide.”**

Chọn trong catalog incentive được duyệt để khuyến khích dịch giờ/địa điểm sạc trong giới hạn khách chấp nhận. MAINGAU đã tham gia nghiên cứu charging incentives; “gửi discount trong giờ thuận lợi” riêng lẻ không mới. Phần cần chứng minh là **individual feasibility + economics có chủ + recommendation thay đổi khi constraint đổi**.

Chỉ chọn khi mentor xác nhận:

1. Incentive được tính là offer phù hợp challenge, và có catalog/window hợp lệ.
2. Biết sponsor/budget owner, cơ chế trả reward và bên nhận lợi ích.
3. Có dữ liệu khả năng đáp ứng và đường quan sát outcome trong pilot; hackathon có thể dùng replay nếu partner chấp nhận.

Thiếu gate 1/2 hoặc chỉ có giá spot thì không lấy FlexMoment làm hướng chính. Thiếu telemetry trong demo có thể dùng fixture rõ nhãn; phải có đường đo thật dự kiến, không gọi acceptance là energy shifted.

### 5.2 Input/output

Input: customer charging availability, departure deadline, required energy và basis, charger/location compatibility, power/capacity assumption, approved windows, incentive terms/min/cap, funding/budget, permission, preference, baseline option.

Output: incentive ID/version, qualifying window, khả năng đáp ứng, reward calculation, effort/trade-off, budget reservation/preview, channel/timing/tone, alternative không nhận incentive, điều kiện khiến offer bị rút.

Không tự tạo station availability, reservation, battery control hoặc grid forecast. Không dùng spot price thấp để suy ra local grid capacity, carbon thấp hay profit MAINGAU. Tín hiệu thị trường, lưới và terms thương mại là ba nguồn khác nhau; dự án [Grids & Benefits](https://www.unternehmertum.de/landingpages/grids-and-benefits) cũng phân biệt chúng.

### 5.3 Engine khả thi và economics

Với fixture đơn giản, capacity mô hình hóa bằng power × phần giao của thời gian khách có thể sạc, window và deadline. Nếu input là năng lượng tới pin, cần loss/efficiency model phù hợp; không coi kW = kWh. Charging curve, station contention và công suất thực chưa biết phải ghi assumption, không gọi guaranteed delivery.

```text
Candidate qualifies iff:
  location/charger/customer eligible
  AND accepted schedule meets customer's required energy/deadline under stated model
  AND incentive qualifying energy/window/minimum/cap conditions hold
  AND reward is funded and budget feasible
  AND required permissions/policy are confirmed.

Reward = qualifying energy × approved rate, subject to approved caps/terms.
```

Không mặc định session phải nằm hoàn toàn trong window hoặc partial charging được hưởng; lấy đúng incentive terms. Nếu reward = 2 €, đó là chi phí/benefit có điều kiện, không phải 2 € lợi nhuận hệ thống.

Nếu chỉ chọn một customer, kiểm budget là đủ. Nếu batch nhỏ và cần reservation, không overbook cùng ngân sách; trạng thái reservation/idempotency phải rõ. Chưa có backend thực thi thì ghi **budget preview**, không giả đã giữ tiền thật.

### 5.4 Bộ demo Flex

**Fixture chung, không phải incentive MAINGAU:** customer có thể sạc từ 20:00; charger-side energy cần 20 kWh; công suất cố định giả định 11 kW; incentive window 21:00–23:00; phải có ít nhất 20 qualifying kWh trong window, cap 20 kWh; reward 0,10 €/qualifying kWh; funded budget 10 €. Baseline có thể sạc ngoài window, không reward.

| Case | Thay đổi | Expected trong fixture |
|---|---|---|
| F1 | Departure 23:00 | Window có capacity 22 kWh, đủ 20; incentive feasible; reward có điều kiện 2 € |
| F2 | Departure 22:00, mọi thứ khác giữ nguyên | Chỉ 11 kWh trong window, không đạt minimum 20; loại incentive này. Baseline 20:00–22:00 vẫn có thể đáp ứng mobility |
| F3 | F1 nhưng budget còn 1,50 € | Không cấp offer cần 2 €; chọn incentive khác chỉ nếu có trong approved catalog |
| F4 | Window bị hủy/đổi sau review | Card/message cũ STALE; tính lại theo window mới |
| F5 | Customer chưa cho biết deadline/required energy | Hỏi đúng fact trong context hợp lệ; không học từ “người giống họ” để hứa xe sẵn sàng |

Không suy từ F1 rằng discount 0,10 là mức thấp nhất đủ làm khách đổi hành vi. Hệ chỉ chứng minh khả thi theo model; tác động hành vi phải đo riêng.

### 5.5 Scope và pilot

**P0:** một charging use case, một horizon ngắn, 2–3 approved incentives, feasibility engine, budget check, recommendation/message/export, F1–F4. **P1:** batch allocation nhỏ và outcome log. **Không làm:** optimization phần cứng, pricing tự phát, grid forecast, online bandit.

Log tách `recommended → exposed → accepted → redeemed → observed charging`. Pilot đo đủ energy/deadline, qualifying shifted kWh và chi phí reward; muốn incremental shift cần comparison/control phù hợp. Không dùng aggregate kết quả nghiên cứu để train uplift cá nhân giả.

## 6. Hướng C — BillShield: hành động trước vấn đề quyết toán

### 6.1 Ý tưởng và điều kiện chọn

> **“Act on the bill the customer is about to face, before it becomes another support call.”**

Chọn khi partner xác nhận proactive billing care là pain và chấp nhận phạm vi service/offer tương ứng. Không làm lại chatbot nhập meter reading hoặc đổi Abschlag: [Parloa mô tả các workflow này đã có](https://www.parloa.com/customers/maingau/).

Điểm cần chứng minh: trigger có evidence, phân biệt dữ liệu sai/thiếu với chi phí thực, chọn bước xử lý đúng và chỉ chọn offer khi nó phù hợp. Không suy hoàn cảnh tài chính/vulnerability từ usage để thuyết phục upsell.

### 6.2 Dữ liệu và engine

Input: meter/customer/contract linkage, actual vs estimated readings, timestamps/units, meter changes/resets, tariff price phases, base fees, taxes/billing rules và payments/credits đúng period. Thiếu một thành phần quyết định thì `NOT_COMPUTABLE` hoặc task xác minh; không tự điền bằng giá trung bình.

```text
Period energy = valid end reading - valid start reading
               [chỉ khi cùng meter/register/unit và không reset/change chưa xử lý].
Period cost = energy charge over applicable tariff phases + base fees + applicable items.
Settlement balance = period cost - valid payments/credits for the same period.
```

Forecast tương lai là module khác: cần giả định consumption/seasonality/occupancy phù hợp, data coverage và uncertainty. MVP có thể chỉ tính **đối chiếu kỳ có dữ liệu đầy đủ**; nếu vậy đổi pitch thành proactive reconciliation, không nói đã dự báo annual bill.

Actions có thể: xác minh reading, giải thích balance, chuẩn bị payment-plan/Abschlag review theo policy, service handoff hoặc approved tariff offer cho kỳ tương lai. Offer mới không làm giảm ngược chi phí đã phát sinh của kỳ cũ.

### 6.3 Bộ demo Bill

**Fixture kỳ đã đủ dữ liệu:** consumption 900 kWh, 0,30 €/kWh, base fee 3 tháng × 10 €, không có dòng phí khác theo giả định; payments 3 × 80 €.

| Case | Dữ kiện/thay đổi | Expected |
|---|---|---|
| B1 | Các input trên được xác nhận | Cost 300 €, payments 240 €, balance 60 €; giải thích và action review có căn cứ |
| B2 | Reading bị đánh dấu estimated hoặc nghi reset | Chặn kết luận balance chắc chắn; yêu cầu xác minh trước |
| B3 | Payments thành 3 × 100 €, consumption/tariff giữ nguyên | Cost vẫn 300 €, balance 0 €. Không ghi “tiết kiệm 60 € tiền điện” |
| B4 | Có approved offer mới cho kỳ tương lai | So forward cost cùng assumptions; không trừ saving dự kiến vào bill cũ |
| B5 | Contact policy không cho marketing | Service action chỉ theo purpose được phép; không dùng lời nhắc bill để chen offer |

**P0:** một trigger/reconciliation, một bằng chứng reading/tariff, một action hợp lệ, message và export; thêm ít nhất một offer cụ thể nếu partner vẫn yêu cầu NBO. **P1:** bounded forecast có assumptions, comparison future tariff. **No-go:** không có data đủ tính hoặc partner chỉ muốn cross-sell ngay và không chấp nhận service-first.

## 7. Hướng D — MomentPilot độc lập: prove the benefit before the offer

Đây là fallback chắc nhất khi có holdings/catalog/permission mà không có đủ journey hoặc flexibility data. Nó cũng là lõi tái sử dụng của các hướng khác.

> **“MomentPilot proves what changes for the customer before recommending the next offer.”**

### 7.1 Phạm vi

Một customer moment, tối đa hai product families, catalog hẹp; observed/entitled/after-offer ledger; hỏi một fact có ích; offer/channel/timing/tone; review/preflight/export. Giữ activation existing benefit và no-purchase alternatives.

Không chọn nếu partner đã có đầy đủ workflow này và không chỉ ra được một lỗi/pain còn lại. Không cố cứu novelty bằng dashboard batch hoặc tuyên bố causal khi thiếu data.

### 7.2 Ca bắt buộc có sẵn để chuẩn bị

Các ca dưới là arithmetic fixtures, không phải tariff hiện hành. Xem thêm [JSON fixtures đã có](fixtures/MomentPilot-demo-scenarios.json).

| Case | Input synthetic | Expected |
|---|---|---|
| M1 — New benefit | Benefit 160 €/12 tháng, extra costs 90 €, các gates phù hợp | Net 70 € theo assumptions; có thể chọn offer, chưa tự có causal profit |
| M2 — Benefit already active | Như M1 nhưng benefit đã active trong reference | New benefit 0 €, net −90 €; không quảng cáo lại 160 € như lợi ích mua thêm |
| M3 — Activate without purchase | Benefit 3 €/tháng, đủ điều kiện nhưng chưa active, còn 8 tháng đã biết | Chuẩn bị activation; 24 € trong known window, không sale mới |
| M4 — Missing decisive fact | Rate 0,10 €/eligible kWh, extra costs 150 €, usage 600–1.800 | Net −90 tới +30 €; break-even 1.500 kWh; hỏi usage đúng kỳ/bucket |
| M5 — Promo horizon | Reference 20 €/tháng; offer 12 € × 12 tháng rồi 28 € × 12, fee 20 € | Saving 12 tháng 76 €, nhưng tổng 24 tháng −20 €; không giấu phase sau |
| M6 — Gross as net | Gross 160, net 70; draft gọi 160 là net saving | Claim bị chặn dù số 160 tồn tại trong data |

Nếu thiếu terms để dùng rate thật, giữ demo-policy label. Không dùng mẩu marketing có discount 5/10 cent làm luật áp cho mọi hợp đồng.

### 7.3 Acceptance và cắt scope

M1/M2 phải đảo quyết định đúng khi chỉ đổi activation state; M3 có alternative không cần mua; M4 có revision sau trả lời; một offer hợp lệ có message và handoff. Có thể cắt solver, experiment dashboard, extraction định dạng thứ hai. Không cắt money/date correctness và preflight.

## 8. DecisionLab: “Challenge this decision” bên trong hướng được chọn

Đây là tính năng kiểm quyết định, không phải app thứ năm và không phải simulator biết khách nào sẽ mua.

UI cho thay một fact hoặc policy version đã định nghĩa: date, availability, active benefit, incentive budget, reading quality hoặc permission. Backend chạy lại **cùng engine đang dùng**, tạo revision mới, hiển thị:

- Candidate/step/message nào mất hiệu lực và dependency nào gây ra.
- Quyết định cũ/mới và lý do khác nhau.
- Những phần độc lập còn giữ được hoặc được tái tính cùng kết quả.
- Export card cũ đã bị chặn hay chưa.

AI có thể đề xuất ca khó nhưng expected cần người đọc nguồn gán nhãn hoặc oracle độc lập phù hợp. Ca sinh từ engine chỉ là regression theo engine, không tự chứng minh engine đúng nguồn. Không dùng fixture mà ta tự định nghĩa hành vi mua để báo ROI.

**P1:** một panel “change a fact” với 3–5 controls có thật. Nếu chưa kịp UI, chạy case mutations qua API/test report. Không dựng platform testing tổng quát trước core.

## 9. Kiến trúc và hợp đồng dữ liệu dùng khi chốt build

### 9.1 Stack mặc định

Giữ công nghệ đội quen; gợi ý React/TypeScript + FastAPI/Pydantic + SQLite, Decimal/integer cents, một AI provider adapter. Dependency graph nhỏ dùng adjacency lists; không cần graph/vector database riêng. Python/TypeScript shared enums được khóa trước khi AI code song song.

```text
Input adapters → confirmed facts / versioned catalog
→ permission + eligibility gates → bounded planner / candidate engine
→ value or feasibility calculations → selection
→ typed claims + bounded message draft
→ review → fresh preflight → export packet
                    ↘ immutable revisions + decision log ↗
```

### 9.2 Entities tối thiểu

| Entity | Trường cần có |
|---|---|
| SourceSnapshot | id, uri/file locator, hash, version, retrieved_at, effective_scope, data_class |
| FactAssertion | id, key, typed value/unit/period, customer/location scope, evidence span/source, status, revision, confirmed_by |
| Customer/ContractSnapshot | IDs, holdings/pricing/benefits, dates, identity-link status, customer preferences, revision |
| PermissionRecord | customer, purpose, channel, product scope, status, objection, source, effective/withdrawn time, revision |
| ReleasedPolicy/Catalog | id/hash/version, offers/rules/action templates, scope, valid interval, review status, required guards |
| OfferVersion | product/incentive ID, eligibility, required facts, price/reward phases, caps/stacking, expiry, source refs |
| Candidate | offer/action, feasibility TRUE/FALSE/UNKNOWN, blockers, alternative, ledger/constraint refs |
| Plan/Step — chỉ nếu cần | goal, steps, requires, produces_fact_types, dependencies, owner, status, due/earliest dates, source refs |
| ValueLedger | baseline, horizon, units/tax basis, cost lines before/after, benefit ownership, net delta/null, assumptions |
| DecisionRun | case/input revision, policy/catalog hash, dependency versions, candidates, chosen action/offer/channel/timing/tone, status |
| Claim/Message | kind, amount/unit/period/baseline/conditions, ledger/source refs, template, model task/version, validation result |
| Review/Handoff | exact run revision, reviewer, preflight result, export payload, idempotency key, no actual execution unless integrated |

Có thể chỉ dùng subset cho hướng đã chọn. Không build bảng meter/incentive/plan nếu không dùng; giữ contract cho provenance và revision chung.

### 9.3 Trạng thái phải tách

```text
Knowledge status: PROPOSED | CONFIRMED | UNKNOWN | CONFLICTING
Candidate feasibility: TRUE | FALSE | UNKNOWN
Readiness: READY | BLOCKED | NEEDS_CLARIFICATION | NEEDS_POLICY_REVIEW
Review: DRAFT | REVIEWED | STALE | REJECTED
Handoff: NOT_PREPARED | PREVIEW_READY | BLOCKED | EXPORTED
External execution: NOT_EXECUTED | [observed response from a real authorized adapter]
```

“READY” nghĩa chuẩn bị được hành động/offer trong phạm vi đã kiểm, không có nghĩa hợp đồng đã active hoặc dịch vụ chắc chắn bắt đầu. `NO_MARKETING`, `WAIT`, `GAP` và `CONFLICT` không được gộp thành một nhãn quyết định thành công.

### 9.4 Quy tắc correctness bắt buộc

- Chỉ dùng **gói policy/catalog release nguyên phiên bản**, có guard bắt buộc. Lọc riêng các rule APPROVED nhưng bỏ guard chưa duyệt có thể tạo kết quả sai.
- Facts không nhất quán hoặc miền completion rỗng → `INVALID_FACTS`/review, không chọn đại một candidate.
- Chọn record/action candidate trước; kiểm permission, timing, budget và dependency bằng stages rõ. Không cho rule đọc outcome chưa tính.
- Snapshot giữ nguyên cả source refs, fact values, edge/dependency, approval status; không chỉ lưu một ID rồi đọc props mới nhất khi replay.
- Có source conflict chưa phân xử thì candidate bị ảnh hưởng không ready; model không tự chọn nguồn “mới hơn chắc đúng hơn”.
- Trước review/export, atomically so input revision, offer/policy hash, dependency/permission versions, expiry và readiness. Dữ liệu đổi → STALE/re-evaluate.
- Request/response/handoff có idempotency; không tạo hai record export hoặc reservation vì bấm hai lần.
- Money dùng explicit units/cents/Decimal; currency, VAT, thời kỳ, timezone và boundaries phải rõ. Null khác 0.

### 9.5 API tối thiểu

```text
POST /cases/import                    normalize một input/case
GET  /cases/{id}                       snapshot + runs hiện có
POST /cases/{id}/facts/extract         AI đề xuất, chưa confirm
POST /cases/{id}/facts/confirm         người xác nhận, tạo revision mới
POST /cases/{id}/evaluate              run mới, plan nếu có
POST /cases/{id}/changes               fact/policy change + re-evaluate
GET  /runs/{id}                        immutable result + reasons
POST /runs/{id}/message                draft từ allowed claims
POST /runs/{id}/review                 review exact dependency revision
POST /runs/{id}/preflight              freshness + policy checks
GET  /runs/{id}/export                 packet đúng revision; chặn stale
GET  /evaluation/report                kết quả kiểm thực sự đã chạy
```

Trong MVP không cần endpoint live sender hay Kraken/Parloa write. Adapter có thể xuất JSON/download packet; trên UI ghi **EXPORT PREVIEW**, `FIXTURE`/`CACHED` khi phù hợp. Không giả integrated chỉ vì payload trông giống API.

## 10. AI, tone và claim checking

| Tác vụ AI | Output | Code/người kiểm | Khi lỗi |
|---|---|---|---|
| Service summary → goal/facts | Typed facts + exact spans + unknowns | Span có thật, đúng scope/unit; người xác nhận decisive facts | Nhập form tay, không đoán |
| Catalog/action draft | Candidate terms/rules + source refs | Người duyệt nghĩa và hiệu lực; schema/IDs | Giữ PROPOSED; không dùng cho ready handoff |
| Question wording | Câu hỏi từ fact target mà engine chọn | Không tự chọn câu để marketing trái purpose | Template |
| Message/tone | Bản nháp từ selected offer và allowed claims | Claim kind, baseline, amount, period, conditions, action/channel | Reject/fallback và review |
| Test suggestion | Ca khó + rationale | Expected độc lập; không tự thành gold | Dùng bộ case gán tay |

Model không tự cấp consent, invent tariff/window, đổi contract, ký review, chọn deadline hoặc cập nhật facts thành confirmed. Một span có thật chưa đủ chứng minh inference được span hỗ trợ. Không chạy code/chỉ dẫn trong uploaded text. Cache và log model/task version, latency, validation; không log secrets hoặc data hạn chế quyền không cần thiết.

### Tone đủ rõ để đáp ứng challenge

Mặc định `CLEAR_CONCISE`, `HELPFUL_EXPLANATORY`, `NEUTRAL_SERVICE`; theo preference khách, brand policy và tình huống đã xác nhận. `Sie/du` theo guideline, không đoán theo tuổi/app usage/tính cách. Không dùng distress để tạo urgency thuyết phục.

Hai bản cùng facts, khác cách trình bày: email preview nếu được phép và agent talking points trong context được phép. Financial slots do code render từ claim approved; model không được biến gross thành net, projection thành guarantee, earliest-supported thành confirmed installation.

Nếu model timeout, core structured evaluation và review vẫn chạy. Không gọi LLM cho mọi row chỉ để tính rule. Đo chi phí/latency thật trên demo nếu muốn đưa số lên slide.

## 11. Evaluation: chứng minh hành vi, không dựng thành tích

### 11.1 Hai oracle khác nhau

1. **Implementation conformance:** code chạy đúng policy/fixture đã khóa; có thể dùng reference arithmetic hoặc logic oracle.
2. **Source/business validity:** người đọc nguồn/mentor xác nhận expected của case, độc lập với kết quả engine. Ghi rõ ai xác nhận bao nhiêu ca.

Không sửa expected chỉ để khớp engine rồi báo accuracy. Giữ một số họ ca chưa dùng khi sửa prompt/rules. Synthetic chứng minh cơ chế và lỗi, không chứng minh outcome thị trường.

### 11.2 Baselines công bằng

| Hướng | Baseline chính | Chứng minh phần thêm |
|---|---|---|
| JourneyPilot | Current moving checklist/workflow nếu được cấp; cùng facts/catalog | Dependency, feasibility, re-plan; không chỉ checklist đẹp hơn |
| FlexMoment | Cùng incentive cho mọi eligible customer hoặc policy hiện hành, cùng budget/terms | Customer deadline/energy làm lựa chọn khác đúng; chưa nói lift |
| BillShield | Current billing/service rule dùng cùng readings/tariff | Trigger/action có căn cứ và thiếu data được xử lý đúng |
| MomentPilot | Eligibility + approved-template/priority, cùng catalog | Entitled alternative, benefit delta, fees/horizon và useful question |
| AI extraction | Cùng engine với manually confirmed structured facts | Chất lượng/effort extraction; tách lỗi AI khỏi engine |

Không dùng baseline cố ý thiếu nguồn rồi kết luận kiến trúc graph/AI tốt hơn. Nếu baseline đã giải đầy đủ case, ghi đúng kết quả và tìm pain khác.

### 11.3 Bộ kiểm tối thiểu sau khi khóa hướng

Mục tiêu lập kế hoạch: 12–20 ca logic có ý nghĩa + 4–6 failure/integration cases; thêm 3–5 case partner nếu được. Đây không phải số đã đạt. Ưu tiên boundary và harmful failures, không viết test lặp cấu trúc UI.

Ca chung: one completed offer; no candidate; unknown vs false; inconsistent facts; unreviewed policy; stale source/permission; wrong claim type; model timeout; injection text; refresh/reset/export; request repeated.

Ca theo hướng: J1–J5, F1–F5, B1–B5 hoặc M1–M6. Với re-planning, đổi input phải làm đổi engine output; không chỉ đổi câu giải thích. Với permission, card cũ không được export; không lách sang channel khác.

Metric để report: x/y valid decisions, invalid/missing prerequisite count, financial correctness, stale/claim blocks, unknown handling cùng coverage, workflow completion, reviewer corrections, latency/calls/cost nếu đã đo. Không gắn Wilson CI cho mọi metric hoặc suy population accuracy từ ca chọn tay.

Acceptance trước pitch: **ít nhất một offer hợp lệ được handoff preview**, một offer bị loại đúng, một fact change làm quyết định đổi, message phù hợp channel/tone, lịch sử và preflight hoạt động. “Block mọi ca” không là recommender thành công.

## 12. Đội 5 người: một contract chung, một hướng chính

| Owner | Phần chung | Nếu Journey | Nếu Flex | Nếu Bill | Nếu Moment |
|---|---|---|---|---|---|
| A — Decision lead | Shared contract, selection semantics | Planner + dependencies/re-plan | Feasibility + selection | Trigger/action logic | Candidate/benefit selection |
| B — Domain/data | Mentor, catalog, source scope, labels | Action templates/lead times | Incentive terms/sponsor | Meter/tariff/payment semantics | Holding/activation/stacking |
| C — AI | Extraction, question wording, typed messages | Goal/date extraction | Flexibility constraints | Reading/summary extraction | Benefit/context extraction |
| D — Frontend/demo | UI, before/after, reset/video | Plan + decision diff | Window/energy + offer | Bill reconciliation + action | Ledger/alternatives |
| E — Backend/quality | Persistence, APIs, preflight/export, tests | Revision/dependency checks | Budget consistency | Billing arithmetic | Money/date math |

A và E phải phân chia cụ thể ngay 13:00; E không thể vừa làm mọi API vừa toàn bộ math/test. A nhận pure decision functions và unit boundary cases; E sở hữu orchestration/persistence; B gán expected độc lập và kiểm chéo arithmetic/terms. Nếu một người yếu backend, đổi owner theo kỹ năng, không đổi hợp đồng dữ liệu.

### 12.1 Backlog giao cho AI coding

| Task | Owner | Deliverable / acceptance |
|---|---|---|
| T01 | A+B+E | Một normalized case, enums/unknowns/units, expected có căn cứ, schema khóa |
| T02 | B | Released catalog slice và rule/source refs; không chờ toàn data |
| T03 | A | Pure evaluate/planner/feasibility functions cho hướng duy nhất; case core đúng |
| T04 | E | Case/run persistence, review/export, refresh còn dữ liệu |
| T05 | D | Customer → offer/card UI gọi API thật |
| T06 | C | Một extractor + one-question wording + message có typed claims |
| T07 | C+D+E | Một ca xuyên input → offer/channel/tone → review/export |
| T08 | A+E+D | Fact change → run mới; stale artifacts bị chặn |
| T09 | E+B | Preflight, failure handling, expected độc lập và report |
| T10 | D+A | Challenge this decision nếu core đã ổn |
| T11 | B+D+cả đội | Pitch, source/evidence labels, video, clean reset/rehearsal |

AI coding nhận file ownership, schema version, sample input/output và failure cases. Không cho mỗi assistant tự định nghĩa “saving”, “ready”, “consent”, “done”. Người trong đội review diff và chạy kiểm phù hợp; nguồn/policy không được auto-approve bởi code sinh ra.

## 13. Lịch tới pitch và luật cắt scope

| Mốc giờ Frankfurt | Gate bắt buộc | Nếu trượt |
|---|---|---|
| Thứ Hai 12:00–13:00 | Pain + data + một hướng + acceptance + quyền model | Chọn fallback có case hoàn chỉnh; không tranh luận tên tiếp |
| 14:00 | Contract chung, một record thật/synthetic rõ nhãn, policy slice | Giảm data adapter; nhập structured form |
| 16:30 | **Một offer/card qua API, lưu và export được** | Dừng tính năng mới; cả đội tích hợp lát cắt nhỏ |
| 19:00 | **Điểm khác biệt chạy thật**: re-plan / flex deadline / bill evidence / benefit delta | Thu còn 1–2 constraints; bỏ simulator/optimizer/extra screens |
| 22:00 | Mentor walkthrough; channel/tone và message đúng; một ca harmful được chặn | Sửa logic/claims trước polish |
| 00:00 | Khóa schema; preflight/replay ổn; chọn P1 duy nhất nếu còn sức | Không thêm workflow, provider hay data format |
| Thứ Ba 00:00–08:00 | Nghỉ luân phiên, regression, UI/deck | Luôn có người giữ integration; không ép mọi người thức trắng |
| 10:00 | Feature freeze, clean reset | Chỉ fix lỗi chặn demo |
| 10:00–12:00 | Baseline/evaluation, số đo thực, error report | Bỏ claim không có số |
| 12:00–14:00 | Video/local fallback, deck, tập 3 lần | Cắt demo đúng thời lượng chính thức |
| 14:00–15:00 | Buffer, reset; sẵn sàng pitch | Không đổi data/policy không được kiểm lại |

**Thứ tự cắt:** hiệu ứng → batch optimizer → format extraction thứ hai → extra product family → selective invalidation tối ưu → Challenge this decision UI nâng cao. Nếu cắt extraction hoàn toàn, nói rõ data được nhập tay; giữ ít nhất một tác vụ AI có ích nếu phù hợp yêu cầu challenge và thời gian cho phép.

**Không cắt:** một completed offer, source/fixture labels, unknown handling, logic/units đúng, review/persistence, stale/preflight, channel/tone và số report trung thực.

## 14. Demo/pitch theo hướng được chọn

Thời lượng dưới là khung 4 phút để tập, không phải thời lượng chính thức đã xác nhận.

| Thời gian | Journey | Flex | Bill | Moment |
|---|---|---|---|---|
| 0:00–0:25 | Khách chuyển nhà cần internet cho công việc | Hai người giống usage nhưng khác deadline | Một balance có thể thành cuộc gọi bất ngờ | Discount không tự là benefit mới |
| 0:25–1:10 | Goal/facts, prerequisite, offer cụ thể | Approved incentive + F1 feasible | Reading/tariff/payments → reconciliation | M1 offer có net value |
| 1:10–2:10 | Jury đổi date/availability → re-plan | Đổi deadline/budget → offer bị loại đúng | Reading/payment đổi → action/cost đổi đúng | M2 active benefit → không tính lại |
| 2:10–2:55 | New offer + channel/tone/message | Reward/conditions + channel/tone | Service/offer hợp lệ + channel/tone | Activation hoặc useful question |
| 2:55–3:25 | Review/preflight/export + lịch sử | Handoff preview + outcome definitions | Review/export, không nhầm cash flow với saving | Wrong claim/preflight bị block |
| 3:25–4:00 | Số đo thật, limits, pilot ask | Số đo thật, funding, pilot ask | Số đo thật, forecast limits, pilot ask | Số đo thật, curator cost, pilot ask |

Không mở bằng dashboard hàng triệu khách hoặc slideshow kiến trúc. Mở bằng một người, một constraint, một quyết định đổi được. Live swap input phải chạy engine thật; video dự phòng là backup có nhãn, không mô tả như live.

### Câu trả lời Q&A phải giữ đúng

| Câu hỏi | Trả lời ngắn |
|---|---|
| “Is this new?” | “Journeys and decision engines already exist. We demonstrate this specific MAINGAU decision, its constraints, and what must change when the facts change.” |
| “Why not Kraken/Parloa?” | Chỉ nói gap mentor xác nhận; không nói nền tảng kia chỉ executes và không decides nếu chưa biết |
| “Does it improve sales/churn?” | “We have tested decision behaviour. Business impact needs a pilot with a suitable comparison.” |
| “Did you send/change/book it?” | “This prototype produces a reviewed handoff packet.” Chỉ nói integration khi adapter thật chạy và được ủy quyền |
| “What does AI decide?” | “AI extracts and drafts. Given confirmed facts and the released policy, the decision logic is deterministic.” |
| “Why ask another question?” | Chỉ ra candidate/constraint bị phân biệt; không hứa mọi case chỉ cần một câu |
| “What if data is missing?” | UNKNOWN + clarification/review; không tạo price, permission, availability hoặc customer preference |

## 15. Business case và pilot sau hackathon

| Hướng | Giả thuyết giá trị | Đo process trong pilot | Business outcome cần thiết kế đo |
|---|---|---|---|
| Journey | Ít offer chưa khả thi, ít trao đổi lặp | Valid plan, prerequisite omissions, corrections, completion effort | Journey completion, acceptance, retention/contribution phù hợp |
| Flex | Reward đi tới người có khả năng đáp ứng | Feasible rate, deadline violations, budget/qualification errors | Incremental shifted energy net of reward cost và benefit theo sponsor |
| Bill | Chủ động xác minh/giải thích đúng trước contact | Reading issues resolved, correct action, reviewer effort | Avoidable contacts, complaint/retention nếu đủ comparison |
| Moment | Ít double count/offer sai, ít thời gian tự đối chiếu | Calculation validity, benefit activation/corrections, effort | Appropriate acceptance, net contribution theo policy |

Business ROI không bằng customer savings. Tính công curator/rule maintenance, review AI, xử lý gợi ý sai và chi phí integration. Đo một đơn vị công việc không trùng; không cộng thời gian test design vào thời gian agent nếu đã nằm trong cùng measurement.

Pilot mặc định 6 tuần: 1–2 tuần xác nhận policy/data và baseline; 3–4 shadow review; 5–6 đánh giá process và replay một thay đổi lịch sử nếu không có source mới. Conversion/churn hoặc billing cycle chưa mature trong sáu tuần thì kéo follow-up, không ép dashboard hiện outcome chưa xảy ra.

Nếu thử causal policy: xác định eligible population, stable unit/assignment và primary outcome trước treatment; xét carryover/interference, capacity giữa arms và outcome maturity. Không giữ lại service bắt buộc hoặc quyền lợi khách để làm control đẹp. Có thể chỉ viết experiment proposal trong hackathon, không dựng uplift kết quả.

## 16. Permission, privacy và phạm vi handoff

Permission phải theo **purpose + channel + product scope + thời điểm**. Khách hiện hữu không tự cho phép mọi email cross-sell: ngoại lệ của [§7 UWG](https://www.gesetze-im-internet.de/uwg_2004/__7.html) có điều kiện, gồm sản phẩm/dịch vụ tương tự và quyền phản đối. Policy áp dụng cụ thể do MAINGAU xác nhận; không để LLM tự phân loại “similar”.

Không coi inbound, app, push hoặc câu hỏi xin consent là lối bypass. Data được phép đọc cho service không tự được phép dùng cho marketing profiling. Không có channel hợp lệ thì chặn marketing handoff, giữ service theo quyền/ngữ cảnh riêng.

Credits AI không phải quyền chuyển dữ liệu tới mọi provider. Dùng public/synthetic trước; partner data chỉ qua endpoint được phép, tối thiểu dữ liệu cần thiết. Không giữ hồ sơ vĩnh viễn để “học tốt hơn”. UI demo nếu chưa có authentication phải nói rõ reviewer persona là mô phỏng.

Trong phạm vi file này, **không cần gửi message thật, giữ tiền thật, đổi hợp đồng, activate discount hoặc điều khiển sạc**. Một export có review, freshness và evidence là kết quả prototype cụ thể; đường integration production là pilot work.

## 17. Câu hỏi tiếng Anh mang vào deep dive

Ưu tiên hỏi 1–5 trước; các câu sau dùng đúng hướng có tín hiệu tốt.

1. **“Can you show us one customer case where choosing the next offer is difficult today?”**
2. **“Does success mean recommending a product immediately, or can the tool prepare the next feasible offer across several steps?”**
3. **“Which part is not already handled by your Kraken, Parloa, or agent workflows?”**
4. **“Which data, approved offers/actions, and policy constraints can we use today?”**
5. **“What would this prototype need to complete for you to consider a pilot?”**
6. Journey: **“Do we have address availability, service dates, transfer rules and a real example of a plan that had to change?”**
7. Flex: **“Does an incentive count as an offer here? Who funds it, which windows are approved, and how can we observe qualifying charging?”**
8. Bill: **“Is proactive billing care part of the challenge, and do readings, tariffs and payments cover the same period?”**
9. Moment: **“Can we distinguish benefits already active from benefits eligible but not activated?”**
10. **“How are marketing objections and permission represented by purpose and channel? Which data may go to which AI endpoint?”**
11. **“Do historical logs include assignment/control, actual exposure and mature outcomes, or only purchases?”**
12. **“What is the exact pitch duration, judging rubric, and policy on prepared code?”**

Không hỏi chung “Is this a good idea?” rồi coi lời đồng tình là acceptance. Ghi lại case, constraint, output và người xác nhận.

## 18. Checklist khóa hướng và phát hành demo

### Trước khi bắt đầu code song song

- [ ] Một hướng chính, một pain chưa được current workflow giải quyết đầy đủ.
- [ ] Một normalized case và một concrete offer trong approved/demo catalog.
- [ ] Hard gates của hướng đã qua hoặc phần thiếu được gắn nhãn/thu scope.
- [ ] Schema/units/unknowns/readiness/revisions thống nhất; owner rõ.
- [ ] Một acceptance quan sát được và một baseline có nghĩa.
- [ ] Quyền dữ liệu/model, phạm vi export/integration rõ.

### Trước pitch

- [ ] Một offer → channel/timing/tone → message → reviewed export chạy từ reset.
- [ ] Một fact change làm engine output đổi đúng; lịch sử cũ giữ được.
- [ ] Offer/message cũ bị chặn khi dependency, policy hoặc permission đổi.
- [ ] Không nhầm active/eligible; gross/net; payment/cost; model feasibility/guarantee.
- [ ] Không invent prices, dates, incentive windows, identity links, permission hoặc uplift.
- [ ] Expected không chỉ sao từ engine; report ghi x/y, nguồn nhãn, lỗi còn lại.
- [ ] Synthetic/partner/public và fixture/cached/live rõ; chưa tích hợp không nói integrated.
- [ ] Có video, local fallback, reset, rehearsal đúng thời lượng.

## 19. Nguồn và tài liệu làm việc

### Tài liệu nội bộ và bản lịch sử

Tài liệu tổng thể này là điểm bắt đầu. Các bản trong `archive/` chỉ giữ để tra cứu nguồn và lịch sử; fixture chạy thử nằm trong `fixtures/`, PDF nghiên cứu nằm trong `references/`.

- Bản review JourneyPilot/FlexMoment do người dùng gửi ngày 25/10/2026: đầu vào hợp nhất của file này. Các URL upload ký tạm trong review không được dùng lại làm nguồn cho deck.
- [Alternative directions memo](archive/MAINGAU-alternative-directions-decision-memo.md): nghiên cứu và lập luận cho Journey/Flex/Bill/DecisionLab.
- [MomentPilot examiner review và blueprint](archive/MAINGAU-examiner-review-va-product-blueprint.md): ledger, baseline, claim checking, evaluation và caveats chi tiết.
- [MomentPilot team brief](archive/MomentPilot-team-execution-brief.md): backlog cũ, dùng phần tái sử dụng; không tự ép Journey/Flex/Bill theo scope cũ.
- [Arithmetic fixtures JSON](fixtures/MomentPilot-demo-scenarios.json): synthetic, không tariff hiện hành hoặc measured impact.

Bản nghiên cứu lưu offline: [Grids & Benefits](references/Grids-and-Benefits-Final-Review-2026.pdf).

### Nguồn ngoài cho factual claims

| Nguồn | Dùng để | Giới hạn |
|---|---|---|
| [MAINGAU chuyển nhà](https://www.maingau-energie.de/blog/umzug), [FAQ internet](https://www.maingau-energie.de/service/faq-internet) | Availability và quy trình chuyển nhà có thật | Bài blog có nội dung/giá cũ; không lấy làm current terms chung |
| [MAINGAU Vorteilswelt](https://www.maingau-energie.de/maingau-vorteilswelt), [FAQ Autostrom](https://www.maingau-energie.de/service/faq-autostrom), [FAQ mobile](https://www.maingau-energie.de/service/faq-mobilfunk) | Benefit/activation có điều kiện | Cần snapshot partner cho rate/scope/expiry/stacking; vài trang khó trích tự động |
| [Parloa MAINGAU case study](https://www.parloa.com/customers/maingau/) | Capability đã công bố về service, tariff/offer và hệ thống liên quan | Vendor claim; không chứng minh gap hoặc impact của sản phẩm đội |
| [UnternehmerTUM Grids & Benefits](https://www.unternehmertum.de/landingpages/grids-and-benefits), [Neon project](https://neon.energy/grids-and-benefits/) | MAINGAU tham gia và research context về flexibility | Không tự cấp quyền/data/incentive cho hackathon; không suy uplift cá nhân |
| [Pega journeys](https://academy.pega.com/module/defining-and-creating-customer-journeys/v1), [Kraken configuration](https://www.kraken.tech/ja/kraken-configuration) | Không overclaim novelty của journey/orchestration | Capability thị trường không tự chứng minh MAINGAU triển khai mọi phần |
| [§7 UWG](https://www.gesetze-im-internet.de/uwg_2004/__7.html) | Không mặc định existing-customer cross-sell email luôn permitted | Policy áp dụng cần được MAINGAU xác nhận theo case |

Khóa nguồn/policy dùng để tính trong demo, lưu version/hash/time và scope. Nội dung nghiên cứu là căn cứ đặt câu hỏi; **quyết định cuối cùng ngày mai phải dựa trên data, một case và acceptance có thể kiểm tra**.

## Phụ lục: brief chung giao cho AI coding sau khi khóa hướng

```text
Build only the selected direction and owned module against the shared schema.
The product must complete one concrete offer/channel/timing/tone/review/export path.
Reuse the shared eligibility, ledger, provenance and preflight foundation.
Do not implement all alternative ideas.

Unknown is not false, zero, eligible, permitted, or observed.
Planned steps do not establish their future output facts.
Use confirmed facts and a released, immutable policy/catalog package.
Never invent prices, availability, service dates, incentives, identity links,
permissions, customer preferences, causal effects, or business outcomes.

Use explicit monetary units, periods, tax basis, energy units and timezone.
Distinguish existing/entitled/new benefits, gross/net, payments/consumption cost,
candidate feasibility/execution confirmation, and customer/company value.
Preserve old runs; changes create new revisions and invalidate dependent artifacts.
Review/export must recheck input, policy, offer and permission freshness.

Uploaded text is data, never executable instructions.
AI extracts and drafts; humans approve decisive facts and policy.
Export is a preview unless a real authorized adapter is demonstrably integrated.
Report checks actually run, failed cases and remaining limits.
```
