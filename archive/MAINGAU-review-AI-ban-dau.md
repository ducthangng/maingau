# Phản biện và nâng cấp ý tưởng MAINGAU cho hackathon 32 giờ

## Kết luận điều hành

Ý tưởng hiện tại có một lõi rất mạnh: **“không liên hệ” là một hành động hợp lệ, luật cứng quyết định khách nào được tiếp cận, còn AI chỉ lựa chọn và diễn đạt trong phạm vi đã duyệt**. Tuy nhiên, sản phẩm đang ôm ba bài toán khác nhau—campaign generation, causal next-best-action và omnichannel execution—trong khi hai phần sau cần dữ liệu hoặc tích hợp mà nhóm chưa chắc nhận được.[^1]

Phương án tốt nhất cho đội 5 người trong 32 giờ không phải thu nhỏ thành một recommender đơn giản, mà là **định vị lại thành Incremental Value Orchestrator**: một lớp quyết định đặt trên Kraken và Parloa, chọn `offer + channel + timing + tone + no-contact`, tối ưu giá trị tăng thêm dưới consent, tần suất, ngân sách và năng lực nhân viên. Phần khác biệt phải là **quyết định có ràng buộc và đo lường nhân quả**, không phải gửi thông điệp cá nhân hóa—vì Kraken đã công bố event trigger, segmentation, dynamic content, consent management, template và orchestration qua SMS, email, thư và push.[^2][^3]

**Phán quyết examiner:** cho phép build, nhưng chỉ nếu đội bỏ tuyên bố “AI biết uplift thật” khi chưa có dữ liệu đối chứng; thay bằng hai chế độ rõ ràng: `Evidence Mode` khi có log treatment/control và `Launch Mode` khi chỉ có dữ liệu quan sát. Current concept: **68/100**. Phiên bản được thiết kế lại dưới đây: **87/100 về chất lượng hackathon**, với điều kiện có một luồng end-to-end chạy được và demo không dùng số synthetic như bằng chứng kinh doanh.

## Bối cảnh chiến lược

MAINGAU công bố hơn một triệu quan hệ khách hàng tại châu Âu và doanh thu 1,3 tỷ euro năm 2025; quy mô này khiến việc ra quyết định cho từng khách hàng có giá trị hơn một campaign builder thủ công. Danh mục nhiều sản phẩm—năng lượng, Autostrom, internet, mobile và shop—tạo không gian cross-sell, nhưng cũng làm tăng số điều kiện eligibility và khả năng offer sai ngữ cảnh.[^4][^1]

MAINGAU đã chọn Kraken làm nền tảng vận hành và triển khai mô hình Universal Agent, với mục tiêu cho nhân viên góc nhìn 360 độ về tài khoản khách hàng; Kraken cũng tuyên bố nền tảng hỗ trợ tự động hóa customer service và sales. MAINGAU đồng thời đang dùng Parloa cho hội thoại AI động trong customer service. Vì vậy, sản phẩm hackathon không nên giả vờ thay thế CRM, journey builder, contact center hoặc voice agent.[^5][^6][^7]

### Khoảng trống hợp lý

| Tầng | Nền tảng hiện có đã công bố | Khoảng trống nên chiếm lĩnh |
|---|---|---|
| Customer data và service workflow | Kraken, Universal Agent, góc nhìn tài khoản 360 độ[^6] | Không xây lại customer profile hoặc CRM |
| Trigger, segmentation, template, consent và đa kênh | Kraken có event trigger, dynamic content, segmentation, template và orchestration nhiều kênh[^2] | Không lấy “đúng thông điệp, đúng kênh” làm khác biệt duy nhất |
| Hội thoại AI | Parloa cung cấp AI agent cho utilities và có thể tích hợp CRM/CIS[^8] | Không xây voice bot mới |
| Quyết định danh mục | Chưa tìm thấy bằng chứng công khai rằng MAINGAU/Kraken đang tối ưu **incremental contribution** giữa nhiều offer cùng hành động không liên hệ | Xây policy layer: eligibility → incremental value → constrained allocation → decision proof → experiment |

Thông điệp chiến lược nên là: **“Kraken executes journeys; Parloa executes conversations; the proposed engine decides which intervention is worth making—and when silence is more valuable.”** Đây là định vị bổ sung cho hệ sinh thái hiện tại, thay vì một sản phẩm trùng chức năng.

## Chấm ý tưởng hiện tại

| Tiêu chí | Điểm | Phản biện khó tính |
|---|---:|---|
| Khớp challenge | 9/10 | Bao phủ offer, channel, tone và từng khách hàng |
| Giá trị kinh doanh | 8/10 | Quy mô khách hàng và danh mục đa sản phẩm tạo tiềm năng lớn, nhưng chưa có margin/churn baseline thật |
| Khác biệt sản phẩm | 6/10 | “Next message/journey” bị Kraken lấn sân; causal decision và no-contact mới là moat |
| Khả thi 32 giờ | 7/10 | Làm được vertical slice; không thể chứng minh uplift thật nếu thiếu experiment log |
| Tin cậy kỹ thuật | 7/10 | Hard guardrail và decision log tốt; tone inference, uplift và proof engine còn dễ bị overclaim |
| Khả năng demo | 9/10 | Ba khách hàng với ba quyết định khác nhau rất trực quan |
| Khả năng triển khai | 6/10 | Phụ thuộc schema, consent semantics, offer margin và API integration |
| Đo tác động | 7/10 | Thiết kế ba nhóm tốt về ý tưởng nhưng attribution cần sửa |

Điểm mạnh đáng giữ nguyên là: offer chỉ đến từ menu đã duyệt; consent và suppression là cổng cứng; hệ thống có thể abstain; số liệu trong thông điệp không do LLM sáng tác; và mỗi quyết định được ghi log để đánh giá. Đây là nền móng tốt hơn nhiều so với một chatbot marketing.[^1]

## Những lỗi phải sửa

### Uplift chưa chắc tồn tại

Tài liệu đề xuất ước lượng chênh lệch giữa xác suất mua khi được liên hệ và khi không được liên hệ. Điều đó chỉ đáng tin khi lịch sử có treatment/control phù hợp hoặc cơ chế nhận treatment có thể điều chỉnh hợp lý; causal analysis trên dữ liệu quan sát còn cần support và overlap—các khách tương tự phải có khả năng xuất hiện ở cả treatment và control.[^9][^1]

Nếu MAINGAU chỉ đưa lịch sử mua và campaign targeting không ngẫu nhiên, model dễ học **ai vốn đã mua** thay vì **ai mua vì được tác động**. AUC cao hoặc propensity chính xác không giải quyết lỗi này; thậm chí treatment càng dễ dự đoán thì overlap có thể càng yếu.

Cần có hai mode:

- **Evidence Mode:** dùng campaign logs có holdout hoặc randomization; ước lượng heterogeneous treatment effect và báo uncertainty.
- **Launch Mode:** khi thiếu đối chứng, dùng transparent heuristic/propensity để xếp hạng tạm thời, đồng thời thiết kế randomized holdout để bắt đầu thu causal evidence; giao diện phải ghi rõ `uplift not identified`.

### Ba nhóm chưa đủ chặt

Thiết kế `no-offer / old-way / AI` là đúng hướng, nhưng “mỗi khách vào một nhóm cho mọi playbook” tạo nhiễu nếu một khách đủ điều kiện cho nhiều playbook. Tác động của playbook điện nhà có thể bị lẫn với internet hoặc retention.

Thiết kế mạnh hơn:

1. Xác định một **decision point** cụ thể, ví dụ Autostrom customer chưa có household electricity.
2. Đóng băng tập eligible tại thời điểm đó.
3. Randomize theo `customer × decision point × experiment version`.
4. Chỉ định một primary outcome và một attribution window trước khi chạy.
5. Dùng mutually exclusive treatment: holdout, current policy, proposed policy.
6. Không đổi treatment giữa chừng; complaint/withdrawal vẫn được suppress vì an toàn, nhưng phải log protocol deviation.

### “Tone AI” đang được đánh giá quá cao

Chọn ba giọng điệu và điền dữ kiện vào template là tính năng hữu ích, nhưng chưa phải moat. Tone suy ra từ transcript còn có thể nhầm cảm xúc, tạo cảm giác thao túng hoặc dùng dữ liệu ngoài mục đích ban đầu.

Tone nên là **execution attribute**, không phải trụ cột sản phẩm:

- Chỉ dùng taxonomy đã được brand/legal duyệt.
- Không suy luận thuộc tính nhạy cảm hoặc personality.
- Complaint hoặc unresolved service issue luôn ép về service-first tone.
- Message verifier kiểm tra từng claim, price, saving, condition và CTA với fact store.
- Cho phép agent xem “vì sao chọn tone”, sửa và ghi feedback.

### Proof engine phải trung thực

Nếu chỉ có annual consumption, proof engine không được khẳng định mức tiết kiệm chính xác của dynamic tariff. Nó nên trả khoảng giá trị kèm giả định, data completeness và confidence.

Ba mức output nên là:

| Trạng thái | Cách hiển thị |
|---|---|
| Verified | Tính được từ dữ liệu định giá và tiêu thụ đủ |
| Estimated | Có giả định rõ, hiển thị khoảng thay vì một số điểm |
| Not computable | Thiếu dữ liệu; không đưa con số vào message |

LLM chỉ được paraphrase các facts có ID; nếu một con số trong draft không map được về fact store, message bị block.

### Compliance là điều kiện, không phải điểm cộng

Email marketing thường cần consent trước; ngoại lệ cho khách hiện hữu chỉ áp dụng khi đồng thời đáp ứng các điều kiện về địa chỉ thu được trong giao dịch, sản phẩm/dịch vụ tương tự của chính doanh nghiệp, chưa phản đối và luôn được thông báo quyền phản đối. GDPR cũng cho phép data subject phản đối direct marketing bất cứ lúc nào, bao gồm profiling liên quan đến marketing; sau phản đối, dữ liệu không còn được xử lý cho mục đích đó.[^10]

Do đó, `consent=true` là chưa đủ. Eligibility record cần ít nhất:

```text
channel
legal_basis_or_consent_id
consent_scope
collected_at
source
withdrawn_at
marketing_objection
product_similarity_rule
suppression_reason
frequency_window
```

Đây không phải tư vấn pháp lý; policy cụ thể phải do MAINGAU xác nhận. Trong prototype, rule phải cấu hình được thay vì hard-code cách hiểu pháp luật của đội.

## Sản phẩm nên xây

### Tên và định vị

**MomentPilot — Incremental Value Orchestrator for MAINGAU**

> For every eligible customer moment, MomentPilot chooses the intervention with the highest defensible incremental value—or chooses silence—then hands the decision to Kraken, Parloa, or a human agent with evidence and measurement built in.

Tên PrüfGraph-style nặng kỹ thuật không phù hợp bằng một tên gợi đúng business outcome. “Next Best Offer” cũng quá hẹp vì hành động tốt nhất có thể là giải quyết complaint, hỏi consent, chuyển cho agent, đợi hoặc không làm gì.

### Decision object

Đầu ra trung tâm không phải message mà là một đối tượng quyết định có cấu trúc:

```json
{
  "customer_id": "C-1042",
  "moment": "autostrom_usage_rising",
  "action": "offer_home_electricity",
  "alternative": "no_contact",
  "channel": "inbound_voice_followup",
  "timing": "after_service_resolution",
  "tone": "warm_respectful",
  "expected_incremental_value": {
    "lower": 4.10,
    "point": 7.60,
    "upper": 10.20,
    "mode": "evidence"
  },
  "eligibility": "passed",
  "excluded_actions": [
    {"action": "outbound_call", "reason": "no_channel_permission"}
  ],
  "proof": ["FACT-17", "PRICE-2026-04", "CONSENT-882"],
  "experiment": "EXP-AUTOSTROM-01",
  "policy_version": "v0.3"
}
```

Đối tượng này cho phép demo tính tích hợp, reproducibility và auditability mà không cần kết nối hệ thống thật.

### Pipeline quyết định

1. **Moment detection:** phát hiện một số moment rõ ràng từ event data, bắt đầu bằng rule thay vì LLM.
2. **Eligibility gate:** lọc product eligibility, consent, objection, complaint, contact pressure và channel availability.
3. **Candidate action set:** tạo các hành động hợp lệ, luôn gồm `no_contact`.
4. **Incremental value scoring:** dùng uplift nếu có dữ liệu đối chứng; nếu không, Launch Mode dùng score có nhãn hạn chế.
5. **Proof calculation:** tính benefit/cost bằng deterministic code và fact store.
6. **Portfolio optimization:** chọn action trên toàn batch dưới budget, capacity và frequency constraints.
7. **Message realization:** LLM chọn template/tone và diễn đạt facts; verifier block claim lạ.
8. **Decision logging:** lưu candidates, exclusion reasons, score, uncertainty, policy version và assignment.
9. **Experiment dashboard:** so holdout, current policy và proposed policy theo primary metric và guardrail.

## Hàm mục tiêu

Với khách hàng `i` và hành động `a`, prototype có thể tối ưu:

\[
V_{i,a} = \tau^{buy}_{i,a}M_a + \tau^{retain}_{i,a}CLV_i - C_{a} - \Delta R_{i,a}CLV_i.
\]

Trong đó `tau_buy` là thay đổi xác suất mua do hành động, `M` là contribution margin, `tau_retain` là thay đổi xác suất giữ chân, `C` là contact/incentive cost và `Delta R` là annoyance/churn risk tăng thêm. Hành động `no_contact` có giá trị chuẩn bằng 0; một hành động chỉ được chọn nếu lower confidence bound hoặc conservative score vượt ngưỡng.

Bài toán batch:

\[
\max_x \sum_{i,a}x_{i,a}V_{i,a}
\]

với các ràng buộc:

- Tối đa một hành động cho mỗi khách trong decision window.
- Action chỉ được chọn nếu eligibility và channel permission đều hợp lệ.
- Tổng chi phí không vượt campaign budget.
- Số cuộc gọi không vượt agent capacity.
- Contact frequency không vượt policy.
- Holdout assignment không bị treatment.
- Optional guardrail: giới hạn contact-rate disparity trên các nhóm được legal/ethics phê duyệt.

OR-Tools phù hợp để mô hình hóa assignment có cost và capacity; CP-SAT hỗ trợ tìm nghiệm feasible/optimal dưới các ràng buộc, nhưng dùng biến số nguyên nên score thập phân phải scale trước.[^11][^12]

### Không nên tối ưu cùng lúc

Trong MVP, chỉ chọn **một primary objective**. Khuyến nghị là expected incremental contribution margin, với churn, complaint, unsubscribe và service issue làm hard constraint hoặc guardrail. Nếu gộp năm KPI vào weighted sum tùy ý, examiner sẽ hỏi trọng số lấy từ đâu và đội khó bảo vệ.

## Scope 32 giờ

### Lõi bắt buộc

| Module | Kết quả phải chạy được |
|---|---|
| Data contract | Customer, moment, consent, product holding, offer, margin, channel, history |
| Policy gate | Pass/block từng candidate và lý do machine-readable |
| Decision engine | Chọn một action hoặc no-contact cho từng customer |
| Batch optimizer | Tôn trọng budget và call-center capacity |
| Proof card | Benefit, assumptions, facts và uncertainty |
| Message generator | 2–3 tone templates, claim verifier |
| Experiment layer | Deterministic assignment và dashboard ba policy |
| UI | Customer timeline, candidate table, portfolio view và audit log |

### Tính năng tham vọng

Chỉ làm sau khi luồng chính đã tích hợp:

- Transcript-to-moment extraction bằng LLM.
- Natural-language policy editor biên dịch thành JSON rule để CRM specialist duyệt.
- What-if sliders cho budget, call capacity và contact frequency.
- Sensitivity view: quyết định thay đổi thế nào khi uplift hoặc margin giảm.
- Counterfactual explanation: điều kiện tối thiểu nào khiến action khác được chọn.
- Export payload mô phỏng cho Kraken/Parloa.

### Không build

- CRM hoặc customer-360 mới.
- Email/SMS sender thật.
- Voice bot mới.
- Knowledge graph tổng quát cho toàn bộ catalog.
- Contextual bandit chạy online.
- Mô hình churn riêng nếu không có label thật.
- Synthetic persona để tuyên bố customer preference.
- Fine-tuning LLM.

## Phân công năm người

| Người | Quyền sở hữu | Deliverable |
|---|---|---|
| 1 — Product/Data lead | Schema, sample adapter, experiment contract, mentor questions | Dataset chạy được và source-of-truth definitions |
| 2 — Decision ML | Evidence/Launch Mode, uncertainty, candidate scores | API trả score và limitation flags |
| 3 — Rules/Optimization | Eligibility, suppression, CP-SAT allocation | Batch decisions cùng exclusion reasons |
| 4 — LLM/Verification | Moment extraction, message generation, claim checker | Structured output và blocked hallucination demo |
| 5 — Frontend/Integration | UI, API integration, logging, pitch demo | End-to-end application và backup video |

Mỗi module phải có owner duy nhất. Coding agents có thể sinh adapter, UI component, test và boilerplate, nhưng không thay owner quyết định schema. Một shared JSON contract phải được đóng băng sớm; nếu không, tốc độ code tăng nhưng integration debt cũng tăng.

## Lịch thực thi

| Giờ | Mốc | Điều kiện qua cổng |
|---:|---|---|
| 0–1 | Mentor interrogation | Biết primary KPI, dữ liệu, current baseline, consent fields và channel thật |
| 1–2 | Scope freeze | Chọn một moment, 2–4 actions, một KPI, một experiment unit |
| 2–4 | Contract + skeleton | Một customer object đi qua API và hiện trên UI |
| 4–8 | Vertical slice v0 | Eligibility → score → action/no-contact → card |
| 8–12 | Optimization + message | Batch constraints và verified draft hoạt động |
| 12–16 | Experiment + dashboard | Ba policy có assignment và metric definitions |
| 16–20 | Integration freeze | Không thêm module; sửa contract và lỗi luồng |
| 20–24 | Stress tests | Complaint, withdrawn consent, missing data, infeasible capacity |
| 24–27 | UI và narrative | Demo bốn phút không cần giải thích code |
| 27–29 | Real-data substitution | Thay sample bằng dữ liệu đối tác nếu được phép |
| 29–31 | Rehearsal + backup | Ba lần demo liên tiếp, quay video |
| 31–32 | Buffer | Chỉ sửa lỗi chặn demo |

Nếu đến giờ thứ 8 chưa có vertical slice, cắt uplift model trước, giữ Launch Mode với score minh bạch. Nếu đến giờ thứ 16 batch optimizer chưa ổn, dùng greedy allocation deterministic nhưng vẫn giữ capacity và no-contact. Không được cắt eligibility, decision log, no-contact hoặc experiment assignment.

## Demo thắng điểm

### Câu chuyện bốn phút

**0:00–0:25 — Pain:** “A high propensity customer may buy anyway. Another may churn because of one more sales message. Sending more offers is not optimization.”

**0:25–1:00 — Policy creation:** CRM specialist chọn một moment, offer catalog, primary KPI, holdout share, budget và call capacity. Không yêu cầu nhập prompt.

**1:00–2:15 — Ba khách hàng:** 

- Markus có usage Autostrom tăng, eligible cho household electricity, inbound permission hợp lệ; engine chọn offer sau khi service request kết thúc.
- Anna có nhiều offer hợp lệ nhưng call capacity hạn chế; optimizer dành cuộc gọi cho customer có conservative value cao hơn và chuyển Anna sang email hoặc app.
- Peter có complaint chưa giải quyết hoặc marketing objection; mọi sales action bị block và `resolve_service_issue`/`no_contact` thắng.

**2:15–2:50 — Trust:** mở decision card, xem candidate bị loại, uncertainty, proof facts, policy version và message checker. Thử yêu cầu LLM thêm một saving không có trong fact store; hệ thống block nó.

**2:50–3:30 — Portfolio:** thay call capacity từ 100 xuống 20; optimizer tự tái phân bổ kênh và giữ khách giá trị cao, thay vì xếp hạng từng người độc lập.

**3:30–4:00 — Evidence:** dashboard phân biệt clearly giữa simulated demo và observed experiment. Nếu chưa có dữ liệu thật, màn hình nói “impact not yet identified” và cho thấy thiết kế pilot để đo.

### Khoảnh khắc wow

Khoảnh khắc wow không nên là LLM viết câu hay. Hãy cố tình tạo xung đột:

> Customer có propensity mua cao nhất nhưng uplift âm, vừa bị contact gần đây và cuộc gọi đã hết capacity.

Sau một click, hệ thống chọn `no_contact`, giải thích từng lớp và cho thấy portfolio profit cao hơn baseline trên **dữ liệu demo được gắn nhãn simulated**. Điều này truyền tải “sell less, earn more” bằng hành vi hệ thống thay vì khẩu hiệu.

## Baseline cần đánh bại

| Baseline | Vì sao cần |
|---|---|
| Send to all eligible | Chứng minh giá trị của silence và capacity allocation |
| Highest propensity | Phân biệt “likely to buy” với “caused to buy” |
| Current MAINGAU rule/campaign | Chứng minh giá trị incremental so với quy trình thật |
| Random eligible | Sanity check cho offline metric |
| Proposed constrained policy | Sản phẩm của đội |

Không được chỉ so AI với random. Baseline đáng tin nhất là current policy của MAINGAU; nếu mentor không cung cấp, hãy mô tả rõ proxy baseline và không gọi chênh lệch là business uplift thật.

## Chỉ số pilot

### Primary metric

- Incremental contribution margin trên mỗi 1.000 eligible decision points.

### Guardrails

- Complaint rate sau treatment.
- Marketing objection hoặc unsubscribe rate.
- Churn/cancellation trong attribution window.
- Contact frequency violations.
- Invalid offer hoặc unverifiable claim rate.
- Agent handling time và override rate.

### Diagnostic metrics

- Tỷ lệ customers nhận no-contact.
- Tỷ lệ candidate bị loại theo từng rule.
- Tỷ lệ quyết định ở Evidence Mode và Launch Mode.
- Width của uncertainty interval.
- Solver status và percentage budget/capacity used.
- Treatment/control overlap và sample balance.

Không dùng open rate làm KPI chính. Nó đo phản ứng với message, không chứng minh contribution margin hoặc retention tăng thêm.

## Câu hỏi bắt buộc cho mentor

1. **What is the primary business objective: contribution margin, retention, product penetration, or service efficiency?**
2. **Do historical campaigns contain randomized holdouts or untreated eligible customers?**
3. **What is the current policy that must be beaten?**
4. **Which customer, offer, margin, consent, objection, complaint and contact-history fields are available?**
5. **Which channel decisions are already handled by Kraken, and which decision is still manual?**
6. **Can Kraken/Parloa receive an external recommendation payload, or should the prototype export only?**
7. **How is consent represented per channel, purpose and product scope?**
8. **Which offers are legally considered similar products for existing-customer email?**
9. **What agent capacity or campaign budget constraint matters operationally?**
10. **Which single customer moment should a six-week pilot target?**

### Cây quyết định sau deep dive

| Điều nhận được | Cấu hình sản phẩm |
|---|---|
| Treatment/control + outcome + margin | Evidence Mode, uplift + optimizer + experiment dashboard |
| Campaign log không random nhưng có propensity features | Observational estimate với overlap warning; không claim causality |
| Customer snapshot + catalog + consent | Launch Mode, rule score + optimizer + experiment designer |
| Chỉ có văn bản và vài customer examples | Decision workbench với explainable policy; demo architecture, không báo ROI |
| Không có consent/objection fields | Chặn outbound execution; chỉ demo inbound context hoặc data-gap report |

## Pitch đề xuất

### Hook

> **MAINGAU does not need another tool that sends more offers. It needs a decision layer that knows which intervention creates incremental value—and when the best action is silence.**

### 30 giây

> **MomentPilot evaluates every eligible customer moment against approved offers, channel permissions, contact pressure, budget and agent capacity. It estimates incremental—not merely predicted—value when causal evidence exists, selects no-contact when uncertainty or risk is too high, and hands Kraken, Parloa or a human agent a verified decision card. Every action is experiment-ready, so MAINGAU learns which euros were truly created rather than counting customers who would have bought anyway.**

### Câu trả lời khi bị hỏi khó

**“Kraken already does personalization. Why do we need this?”**

> Kraken is the execution and customer-operations platform. MomentPilot is a portfolio decision layer that compares interventions against no-contact, optimizes scarce capacity and designs the evidence needed to measure incremental value.

**“How can you know uplift in one day?”**

> We cannot infer credible uplift without suitable historical controls. The product detects whether causal evidence is available. Otherwise it enters Launch Mode, labels the estimate as non-causal and creates the randomized holdout needed to learn safely.

**“Is this production-ready?”**

> The prototype proves the decision contract, hard eligibility gates, constrained allocation, verified communication and experiment design. Production readiness still requires MAINGAU policy approval, data validation and integration testing.

**“Why use an LLM?”**

> The LLM extracts context and realizes approved content. It never creates eligibility, prices, savings or the final action. Deterministic policy and optimization remain authoritative.

**“What is the moat?”**

> The moat is not text generation. It is the compounding decision log linking customer moment, eligible alternatives, causal evidence, operational constraints, outcome and policy version.

## Tiêu chí phê duyệt cuối

Examiner nên chấp nhận sản phẩm nếu demo đáp ứng đủ sáu điều:

- Một customer đi xuyên luồng từ event tới action/no-contact.
- Mỗi action bị loại có lý do rõ ràng.
- Portfolio optimizer phản ứng với ít nhất hai constraint thật.
- LLM không thể đưa claim ngoài fact store vào message.
- Dashboard không đánh tráo simulated result thành observed impact.
- Pitch chỉ rõ sản phẩm bổ sung cho Kraken/Parloa ở tầng nào.

Nếu thiếu một trong ba yếu tố `no-contact`, `hard eligibility` hoặc `experiment-ready logging`, sản phẩm sẽ rơi về một recommender marketing quen thuộc. Nếu giữ được cả ba và thêm constrained portfolio optimization, đây là một ý tưởng đủ tham vọng cho năm người trong 32 giờ, khác biệt rõ, có đường pilot thực tế và bảo vệ được trước examiner khó tính.

---

## References

1. [MAINGAU-ho-so-cong-ty-va-de-xuat-san-pham-Next-Best-Offer.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/71097212/e6ca3bf8-c26f-4ec6-988a-5d22bd81ab29/MAINGAU-ho-so-cong-ty-va-de-xuat-san-pham-Next-Best-Offer.pdf?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Checksum-Mode=ENABLED&X-Amz-Credential=ASIA2F3EMEYEYLXIB3UM%2F20261025%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20261025T162811Z&X-Amz-Expires=3298&X-Amz-Security-Token=IQoJb3JpZ2luX2VjEPn%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaCXVzLWVhc3QtMSJIMEYCIQDremV6oEOgdwdT3KL7j8t%2FH0ACNZ0JqiK7PRjZ4oBfSAIhAKXnf2r5s%2F7bBsPMsbpBBonwUlTLLI3dgf6K6T%2FlhjqHKokFCMH%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEQARoMNjk5NzUzMzA5NzA1IgxFwuybJWNb3H1nawgq3QTIcJrrYaYsT8SWLqsOBforXfQqObyy9WqBTiz0fzFPkuWpaNFnVZXuerXL0tmTVtDlNCxSyQKszTmlIK39B3%2FnIJbEZhTUjISckZctn65AXcjTfMA0Rk8ynh54PpYprNCml6Vwe1QhMq3slOGd2juTlUPNndD1WkiVObDwwqo%2FPBUMoM8mMtzmACuKciUmkeZvHBJfIl0%2FIE2iJrQZ%2BsSyve5%2BWQexz0SOx0im28ApJG2Y93tHTsfvs0eZMncON%2BT%2FmoyOu6cXWyIG9SpA%2BG1%2FUYvy5VWMJ%2FNz7He%2FEOBZSX3PetNirbeRTwIHAyxyNSofmroH0oWvLoGxVbrqu0ek6GmFYk2Os2%2BaO%2B1KeCJiA61oJHBsH%2BzqL861LvqVtfGRv%2BJ2H%2BSaftf%2FmuckEyVG2HlpGeHr0COmoc0BDTFrjlK2ESEGmeA9dFU1Rau2pPPol5shUBSBll%2Fu81sbz1nFVbxbec6COl%2BzGaPuCRL%2FoEJ5dIU0Xa2Wa17D48pygJSDzpYzr3qZ6PjSXOowLyISXEX6OJpFn9%2B8gHqElm7ziCSplEOm%2BVx6idqJqaGaK792FhIuhXnpOZNalx0IXIgkWI8KgbKzBnpml8Le%2FB%2FUooXMBHeYW9F%2BILidiFYOeqzLtAjxQoKS5l%2FhGGSaLwpS%2FuwZh%2FDZt77WYGNo8c4L%2FJnT%2FrK9uRl8B%2BCj2BM2tB9QTOjUAZdqDQ1xtuE1ILjLuGUwfe4thSks9Ke71PxPDUku36ER%2FlFE%2FEZ3thfB8boCpHfu13%2B3hddThlTRB%2B6KF904h%2Fsel4KkjixfhDCq2vjWBjqXAUESz9MwTWbXfDQGvGoE8L0ds6ZRh2dwyc0zpm2AilZfjcH3Jq%2F5CMqe%2B6rXVJHscgqxXS2Myj%2FTwUEuIn8k4xUq2iXHO7LQ0ziH4ARbHGiq6F%2FpOd1SuAnL%2B7f2nHD%2FqGpypuoRjHd%2FHRdJjHk0VC4qUHizHve9hrTR7GfFllRyOu99qg2KEDIM5MD35z%2Bk2XHAaRbIgic%3D&X-Amz-SignedHeaders=host&x-id=GetObject&X-Amz-Signature=4b8c0cff732c5dfae2a040aeca2a8a03437393062af64acafbc7d4e01e4f11fb) - MAINGAU h s cng ty v xut sn phm Next Best Offer

2. [Latest releases | Kraken](https://www.kraken.tech/ja/product-updates) - Directly integrate with smart thermostats to help residents and utilities avoid energy use during pe...

3. [Kraken Configuration | Kraken | Kraken](https://www.kraken.tech/ja/kraken-configuration) - Build your own sales funnels, automate assignment rules and track progress from first contact to fin...

4. [Über uns | MAINGAU](https://www.maingau-energie.de/ueber-uns) - Mehr als **1.000.000 Kundenbeziehungen** europaweit und ein Umsatz von **1,3 Milliarden Euro in 2025...

5. [Voice AI Agents für Energieversorger](https://www.parloa.com/de/loesungen-nach-branche/versorger/) - 24/7 Kundenservice mit AI
...
> Carsten Streitzig

6. [Kraken to unleash digital transformation for Germany’s ...](https://www.kraken.tech/press-releases/kraken-to-unleash-digital-transformation-for-maingau) - In addition to the Kraken platform, the deal will also see Kraken roll out its “universal agent” ope...

7. [About Parloa | The AI Agent Management Platform Company](https://www.parloa.com/company/about/) - As a modern energy company, we aim to adopt forward-looking technology early and lead the way, and P...

8. [Voice AI Agents for Utilities Customer Service - Parloa](https://www.parloa.com/solutions-by-industry/utilities/) - AI agents scale to your contact volume, whether to answer billing questions, provide service updates...

9. [Assessing Support and Overlap with OverRule](https://www.pywhy.org/dowhy/v0.12/example_notebooks/dowhy_refuter_assess_overlap.html) - Before running any causal analysis, we first check for support and overlap. Note that the default se...

10. [Bürgerservice](https://www.gesetze-bayern.de/Content/Document/Y-300-Z-GRURRS-B-2022-N-36507?hl=true) - Es muss nach der Bestellung zu einem Verkauf gekommen sein (Köhler, aaO, § 7 UWG, Rn. 204a).

11. [Solving an Assignment Problem | OR-Tools](https://developers.google.com/optimization/assignment/assignment_example) - - It leverages either Mixed Integer Programming (MIP) with the SCIP solver or Constraint Programming...

12. [Assignment with Task Sizes | OR-Tools](https://developers.google.com/optimization/assignment/assignment_cp) - - The code addresses the Generalized Assignment Problem, optimizing task assignments to workers with...

