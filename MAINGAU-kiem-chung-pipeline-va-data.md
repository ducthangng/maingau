# MAINGAU: kiểm chứng pipeline, challenge thật và dữ liệu

Ngày 26/10/2026. Đối tượng chính: [pipeline hiện tại](MAINGAU-pipeline-va-diem-khac-biet.md), toàn bộ 287 dòng, cùng năm diagram Mermaid, challenge PDF, 23 sheet workbook và toàn bộ 647 dòng JSONL. Bản pipeline được audit có SHA-256 bắt đầu `8531e3ecb04f2d77`; hash đầy đủ trong evidence đi kèm.

## 1. Phán quyết examiner

**Giữ hướng NBA và deep dive B. Đây là phương án đúng đề và có thể build với năm người. Chưa duyệt nguyên trạng đặc tả để khẳng định “luôn đúng” hoặc “0 vi phạm”.** Phần đọc đề và phần lớn thống kê khá chính xác; rủi ro lớn nằm ở ngữ nghĩa thời gian, eligibility, xác suất và việc kiểm lại quyết định lúc sử dụng.

Với đề thật, không nên quay lại JourneyPilot/FlexMoment/BillShield làm sản phẩm chính. Đề đã định nghĩa “best” là expected ΔCLV, yêu cầu cả ba giao diện và có khách tham chiếu ẩn. Có thể giữ tư duy re-planning và decision proof của các idea cũ, nhưng phải phục vụ NBA trên dataset được cấp.

Không có mã nguồn engine, policy JSON hay ứng dụng trong thư mục đang review. Vì vậy audit này kiểm **nguồn, số liệu và logic thiết kế**; không phải kết quả chạy thử một implementation. “Thu hồi trong vài giây”, “tính lại đúng” và “zero violations” hiện là acceptance cần chứng minh.

### Kết luận theo từng trục

| Trục | Kết luận |
|---|---|
| Khớp challenge | Tốt: offer/channel/Du–Sie/ΔCLV/reason; marketing + Customer 360; chọn B; pitch 8+4; architecture Databricks/MCP |
| Phù hợp dữ liệu | Tốt ở số liệu nền; chưa xử lý hết các bất nhất thời gian và thiếu lịch sử |
| Tính đúng quyết định | Chưa khép kín: kênh ảnh hưởng score nhưng chọn sau; service/holdout/prior chưa định nghĩa đủ |
| Tính mới | KG, explainability, service-first và replay đều là cơ chế quen hoặc đã nằm trong đề; khác biệt phải nằm ở chứng minh sâu, tích hợp và khả năng marketer thay policy |
| Khả thi | Có nếu dùng một decision backend cho ba view, graph nhỏ và replay local; sẽ quá tải nếu làm framework ontology, online learning và Databricks thật cùng lúc |
| Khả năng bảo vệ trước jury | Mạnh hơn sau khi sửa các điểm dưới; hiện một số câu demo có thể bị bác ngay bằng data |

## 2. Đã kiểm những nguồn nào?

- [Challenge thật, 13 trang](Hackathon_slides_for_MAINGAU.pdf): đọc toàn văn, xem contact sheet toàn bộ và trang hard rules ở độ phân giải đủ đọc.
- [Workbook gốc](data/maingau_nba_mockdata.xlsx): đọc toàn bộ các sheet bằng chế độ read-only, kiểm count, PK, FK customer, dictionary, CLV, consent, histories và các khách demo.
- [Stream gốc](data/event_stream_2026-10-01.jsonl): parse tất cả dòng, dedup, kiểm payload, thời gian và tình huống demo.
- [Năm diagram](diagrams/): kiểm semantics so với file pipeline và nguồn.
- Tài liệu pre-challenge trong thư mục và archive dùng làm lịch sử thiết kế; không thay challenge mới.

Script kiểm chứng đọc lại trực tiếp workbook/JSONL: [audit_data.py](review-artifacts/pipeline-audit-2026-10-26/audit_data.py). Kết quả, hash nguồn, counts và phản ví dụ công thức: [audit-results.json](review-artifacts/pipeline-audit-2026-10-26/audit-results.json).

Workbook và JSONL được giữ nguyên. Không suy số liệu mock thành thực trạng vận hành của khách hàng MAINGAU thật. Không scrape hệ thống MAINGAU.

## 3. Đối chiếu challenge: những gì đang hiểu đúng

| Nội dung pipeline | Nguồn challenge | Đánh giá |
|---|---|---|
| “Best” theo expected CLV gain | Trang 6–7 | Đúng. Không đổi objective thành cost saving cho khách hoặc affinity đơn thuần |
| Formula có accept/reject | Trang 7 dùng bản rút gọn; sheet `clv_method` dùng bản đủ | Dùng bản đầy đủ của workbook là hợp lý; không phải tự thêm công thức trái đề |
| Consent/exclusions trước ranking | Trang 8–9, 12 | Đúng; hard rules không được lever/HITL override |
| Ba view engine/marketing/Customer 360 | Trang 10–11 | Bắt buộc, không phải ba app độc lập |
| Databricks + MCP một slide | Trang 10–11 | Đúng; không yêu cầu phải deploy thật để thay slide |
| 8 phút + 4 phút Q&A; weights 25/25/25/15/10 | Trang 11 | Đúng |
| Chọn một deep dive; B = freshness/replay | Trang 11 | Đúng; Learn ở mức concept được chấp nhận ở trang 8 |
| No autonomous sending, German customer content | Trang 12 | Đúng. Bảy preference `en` là câu hỏi policy; mặc định challenge yêu cầu tiếng Đức |
| Integration đã được giả lập bằng unified customer_id | Trang 5 | Đúng. Không dành nửa thời gian thi xây data integration platform |

Điều slide **không** chốt thay đội: mapping đầy đủ channel→consent, treatment của service/inbound, contact cap cụ thể, cách xử lý pending cancellation với retention, prior cho action không có history và các mâu thuẫn snapshot. Phải ghi assumption hoặc hỏi mentor.

## 4. Số liệu tính lại: đúng, có điều kiện và cần sửa

| Claim trong pipeline | Kết quả kiểm chứng | Cách dùng đúng |
|---|---|---|
| 750 khách | Đúng; customer_master/customer_value đều 750, customer PK duy nhất | Dùng được |
| 16 bảng | Slide ghi 16, README ghi 15 source tables; file thực có **23 sheet, 18 dòng source registry** | Nói “750 khách, 18 bảng được liệt kê trong sources, 23 sheet kể cả metadata/assumptions” khi mô tả file thực |
| 647 dòng → 635 event, 12 duplicate | Đúng; duplicate cùng ID có payload giống nhau | Không cắt tùy ý về 640 chỉ để khớp slide |
| 100 event out of order | Có **100 lần timestamp occurred_at lùi giữa hai event kề nhau trong ingestion order** | Ghi đúng định nghĩa; không tự gọi đó là 100 lỗi cập nhật cùng một state key |
| Delay tối đa 47 giờ | Chính xác hơn: **47,2625 giờ**; event cuối được nạp 03/10 19:27:39 | Replay phải chạy hết arrival horizon, không dừng nửa đêm 01/10 |
| 67 blocked snapshot = union của 31 dunning, 29 complaint, 8 cancellation | Đúng khi đọc `status` nguyên file; có overlap giữa nhóm | Không cộng 31+29+8 thành unique count; xem bất nhất snapshot ở mục 5.3 |
| 461 profiling granted / 289 không; phone 125, SMS 75 | Đúng | Portal/app còn 582 granted; đừng bỏ sót kênh này |
| 2.270 action; control 248; conversion 3,4% vs 2,0% | Đúng: **69/2.022** delivered và **5/248** control | Là descriptive mock rates, chưa là causal uplift |
| 8 action chưa có history | Đúng: EN-01/03/04, MO-03, SL-02/03, SH-04, SV-01 | Service fix và StromAktiv đều cần xác suất/assumption có nhãn |
| 334 delivered sau consent withdrawal | Tái tạo đúng với mapping trong script và `updated_at < decided_at` | Mapping portal/app cần mentor xác nhận; đây là mock legacy diagnostic, không “334 khách thật bị gửi trái luật” |
| 70 newsletter actions sau unsubscribe | Tái tạo được **70 action sau ngày gửi một campaign có flag unsubscribed** | Không có `unsubscribe_at`; chưa đủ chứng minh 70 action đều sau thời điểm unsubscribe thực |
| 72/203 Autostrom gửi cho người đã có | 72 là holders **ở snapshot**; kiểm start_date trước action còn **70/203** | Dùng 70 với phạm vi kiểm start_date/status hiện có; không coi snapshot holdings là lịch sử đầy đủ |
| 81 sales actions tới khách đang nợ | 81 delivered tới khách **đang dunning ở snapshot** | Không có `dunning_since`; chưa biết cả 81 đang nợ tại lúc action được gửi |
| 1.589 machine opens, 1.457 human opens | Đúng trong `newsletter_performance` | Chỉ bỏ machine-open khỏi tín hiệu engagement; giữ click/conversion nếu có trong cùng dòng |
| 55/100 feedback bị bỏ, 30 vì upset | Đúng nếu nói **55 dismissed**; còn **11 ignored**, 34 accepted bởi agent | Agent accepted không đồng nghĩa khách accept/mua |
| 25 mẫu Du/Sie, 320 Sie/238 Du | Có **559 message_text không rỗng, 24 text khác nhau**, gồm một mẫu tiếng Anh | 320/238 là nhãn heuristic do đội suy ra, không ground truth được workbook gán sẵn |
| Khoảng 150 Autostrom-only | README nói 150; theo active Autostrom và không active energy/mobile/HEMS còn **126** | Cần định nghĩa “only”; không dùng 150 như count đã kiểm đúng file mới |
| 452 có điện chưa có mobile; data-limit ≥2/3 tháng: 11; gas deregistration: 12+1 | Tái tạo được | Nói rõ active status và mốc as-of |
| Price guarantee <90d: 144 | Tái tạo 144 khách khi đánh giá tại **01/10/2026**, điều kiện 0≤days<90 | Chốt evaluation clock; 30/09 với <90d cho count khác |
| CLV reconstruction median error 0,27 € | Đúng: median **0,2712 €**, max **3,0461 €**, 31/750 sai số >1 € | Đừng chỉ báo median rồi hứa khớp tuyệt đối |

PK kiểm ở các bảng có khóa định danh rõ không có duplicate trong lần kiểm này; không có FK customer lạ ngoài 25 shop order lines có customer_id null như data trap dự kiến. Shop là order **line**, không tự dedup toàn bộ theo order_id nếu có nhiều dòng hợp lệ.

## 5. Những điểm phải sửa trước demo và trước khi khóa code

### 5.1 Score phải được tính trên action × channel, không chọn kênh sau cùng

**Dòng 58–67, 105–107.** p_accept được học theo offer/channel/tone; contact cost cũng phụ thuộc kênh. Nhưng pipeline chọn action ở ⑤–⑥ rồi mới chọn channel ở ⑦. Cổng consent ở ④ cũng chưa biết đang xét channel nào. Nếu không định nghĩa bước nội bộ, thuật toán đang thiếu dữ kiện để tính score đúng.

**Sửa:** tạo tuples `(action, allowed_channel, permitted_tone)` trước scoring. Loại tuple không hợp lệ, tính ΔCLV cho từng tuple, rồi chọn max. Nếu tone đã được quyết bằng preference/context, cố định nó trước khi score. UI vẫn có thể trình bày channel/tone ở bước sau, nhưng tính toán đã phải biết chúng.

Ví dụ cơ chế: cùng acceptance gain 100 €, email p=.02/cost=.01 cho 1,99 €; call p=.10/cost=6 cho 4 €. “Chọn kênh hay dùng nhất” sau ranking không bảo toàn expected ΔCLV tối đa. Đây là ví dụ minh họa, không phải estimate một khách MAINGAU.

### 5.2 Profiling gate phải có trước sử dụng hành vi để personalize

**Dòng 55–59, 172, 185, 204, 270–271.** Tài liệu đặt candidate generation từ behavior trước profiling gate và nhấn nhiều vào tone fallback Sie. Nhưng trang 12 yêu cầu personalisation chỉ cho khách đồng ý profiling. Giữ Sie không làm recommendation dựa trên lịch sử hành vi trở thành không personalized.

**Sửa:** kiểm quyền dùng feature trước extraction/profile/candidate/scoring cá nhân hóa; sau đó kiểm channel cho từng tuple. Với 289 khách không granted profiling, định nghĩa rõ fallback không cá nhân hóa/service theo policy mentor xác nhận. Unknown không thành permitted. Không lấy số card output cao làm lý do bypass.

Thu hồi profiling của MG-100003 phải chạm mọi personalized marketing recommendation liên quan, không chỉ newsletter và Du/Sie. Marketing email còn granted cũng không tự cứu recommendation dựa trên profiling đã withdrawn.

### 5.3 “Snapshot 30/09” có dữ kiện tương lai: phải chốt cách replay

**Dòng 40–50, 82, 239.** Workbook chứa:

- **79 charge_sessions có `cdr_received_at` sau cutoff 30/09 23:59:59**, liên quan 69 khách; một là failed session.
- **15 sessions kết thúc sau cutoff**.
- `TK-200565` của **MG-100562**, category complaint, `status=closed` nhưng `resolved_at=02/10 04:40:54`.
- `TK-200640` của **MG-100655**, category autostrom, `status=closed` nhưng `resolved_at=01/10 20:11:22`.

Nếu tái dựng complaint tại cutoff từ created/resolved timestamps, số khách complaint mở là **30**, trong khi đọc cột status trực tiếp cho 29. Đây là bất nhất ở mock source, không phải lỗi đã chứng minh của implementation đội.

**Sửa:** hỏi Raphael chọn semantics đánh giá. Giữ hai khái niệm rõ:

| View | Cách hiểu |
|---|---|
| Provided snapshot | Cột state/CLV được cung cấp là baseline authoritative cho benchmark; hiển thị source inconsistency |
| Strict as-of replay | Chỉ dùng facts đã có thể biết tại knowledge cutoff; reconstruct event/ticket time và CDR arrival theo policy được chốt |

Không âm thầm sửa input rồi so với hidden reference như không có khác biệt. Không dùng late CDR, future resolution hoặc 14-day outcome tương lai để làm replay trông chính xác. Nếu dùng precomputed customer_value làm baseline mặc dù chi tiết nguồn có timestamp khác, ghi rõ đây là model snapshot được cung cấp, không tuyên bố đã tái tạo mọi source as-of.

### 5.4 Không thể biết event trước khi nó được nạp; không thể thu hồi thứ đã gửi

**Dòng 19, 82–95, D1 và câu chốt 147.** Cancellation của MG-100465 xảy ra 01/10 09:17:48 nhưng đến 02/10 02:11:06 mới biết: trễ **16 giờ 53 phút 18 giây**. Engine không thể tự biết cancellation trong khoảng đó nếu không có một source khác. Sau arrival có thể thu hồi pending card, nhưng không thể xóa một communication đã delivered trong quá khứ.

**Sửa:** tách ba phép đo:

1. **Arrival-to-invalidation:** từ khi event nạp tới khi pending recommendation không còn dùng được.
2. **Decision-time known-state validity:** có vi phạm state/policy đã biết lúc review/export hay không.
3. **Retrospective late-data exposure:** action nào hóa ra gặp sự kiện bất lợi đã xảy ra nhưng chưa được source báo.

Replay online theo **ingested_at**, giữ occurred_at để cập nhật đúng fact. Nếu sort toàn bộ theo occurred_at, phải gọi là hindsight replay; nó không chứng minh online correctness. Kiểm invariants sau **mỗi** transition và tại preflight, không chỉ lúc stream đã chạy xong.

Update timestamp phải theo **fact/entity key**, không một `last_event_time` cho cả customer. MG-100004 có ticket event mới hơn theo business time nhưng dunning cũ hơn đến hôm sau vẫn phải cập nhật dunning. Tie-break và event ID conflict cần định nghĩa; duplicate cùng ID không được tăng count/cost lần nữa.

Thêm **effective time** khi payload có: gas deregistration của MG-100125 nhận 02/10, `effective_date=31/10`. Có thể tạo pending/interest signal trước đó, nhưng không tự xóa gas holding/margin từ 01/10.

Freshness cần **source watermark/last successful sync**, không chỉ `record_updated_at`: một consent không đổi từ năm 2017 vẫn có thể là trạng thái hiện tại trong feed vừa đồng bộ. `sources.typical_latency` là mô tả độ trễ, không phải timestamp chứng minh feed đang hoạt động hoặc SLA đã đạt. Thiết kế stale thresholds theo source/action, ghi dependency nào đang chặn; event thời gian trôi qua cũng có thể đổi expiry/90-day windows dù không có customer event mới.

### 5.5 Chốt mô hình CLV và các biến thể action thành pure functions

**Dòng 62, 189, 207, 243.** Công thức kỳ vọng đúng theo `clv_method`, nhưng transformation của action chưa đủ để code nhất quán.

| Vấn đề | Cần chốt |
|---|---|
| Raw CLV được làm tròn, churn hiển thị bị làm tròn | Tính before/after trên cùng precision/model; không trừ raw rounded CLV khỏi một after tính khác basis rồi gọi chênh lệch nhỏ là gain thật |
| Recurring vs one-off | Shop margin 90/126/23/9 chỉ tính một lần theo timing đã chọn; không cộng vào annual margin 10 năm |
| Retention | Chỉ bỏ đúng driver price-guarantee đang có; không giảm .10 cho mọi khách; không vừa bỏ driver vừa áp cùng effect lần nữa |
| Service | Loại driver nào, cost-to-serve tương lai đổi hay không, success probability là gì, 15 € nằm trong success branch hay là cost thực hiện phải trả? Workbook chưa định nghĩa hết |
| Rejection penalty | Workbook nêu sales contact trong **open complaint hoặc dunning**; không mặc định mọi ticket hoặc failed charge đều có cùng penalty |
| Extra business line | Catalog action effect vs multi-line factor vs thêm 12 €/năm cost: không áp trùng; hỏi mentor, version assumption |
| NO_ACTION | Baseline ΔCLV=0/contact cost=0 phải riêng với P-SV-01 active service fix có chi phí và effect |
| Existing churn drivers | Failed charges ≥3 là threshold; từ 3 lên 4 không tự cộng thêm .10 lần nữa |

Pure scoring function phải nhận `value_model_version`, assumptions, probability source, channel và customer state revision. Ghi từng thành phần accept/reject/contact/service cost, không chỉ một số cuối. Với probabilities/parameters giả định, nhãn là **model-based expected ΔCLV**, không causal uplift đã đo.

### 5.6 Cách học p_accept hiện tại có thể bị lọc sai và rò rỉ tương lai

**Dòng 76, 111, 145, 243.** Có 2.022 delivered nhưng chỉ 69 conversions; 8 catalog actions không có lịch sử; P-AS-01 có 203 delivered và **0 conversions**. Cell offer×channel×tone rất thưa.

Các sửa bắt buộc:

- `converted_within_14d` là conversion outcome, không tự là “khách đồng ý”; `agent_action=accepted` là agent nhận gợi ý. Không trộn hai loại nhãn.
- Nếu mô phỏng học tại cutoff 30/09, **223/2.270** actions chưa đủ 14 ngày follow-up; trong delivered là **189/2.022**. Không lấy nhãn tương lai như đã biết tại cutoff. Có thể dùng full-data retrospective rate cho prototype nếu ghi rõ mode, không gọi đó là as-of learning.
- “Chỉ học khách chưa có sản phẩm” phải kiểm **eligibility ở decision time và action type**. Upsell cần khách đang có sản phẩm gốc. Lọc theo holdings hiện tại có thể loại nhầm người vừa mua thành công và gây selection bias.
- Dùng backoff/shrinkage có nhãn, ví dụ tuple → offer/channel → offer → global/category prior. Định nghĩa pseudocounts và sensitivity; không hứa posterior là causal estimate.
- P-SV-01 cần xác suất thực hiện/giải quyết service phù hợp, không áp global purchase conversion ≈3,4% như một quy luật. Prior khác nhau phải được ghi là assumption.
- 248 control rows không phải 248 khách holdout ổn định: **207 customers xuất hiện ở cả control lẫn delivered histories**. Có thể phân tích theo decision point nếu xử lý thiết kế phù hợp; không gọi đó là randomized stable-customer experiment.
- Trong prototype B, freeze probability version. Phần Learn trình bày concept là đủ; không tự online-update score bằng mỗi feedback event rồi phá khả năng replay.

### 5.7 Marketing approval chưa phải quyền sử dụng một card mãi mãi

**Dòng 71–74, 85, 120, diagram 02.** Cần chặn stale ngay tại review/use/export và mỗi customer trong batch. Không có bước này thì UI thu hồi đúng nhưng một payload/cached card cũ vẫn có thể được dùng.

State tối thiểu: `PROPOSED → APPROVED → EXPORTED`, cùng `REVOKED / SUPERSEDED / EXPIRED`. Mỗi record giữ input revision, policy/probability version, consent revision và evidence IDs. Preflight compare-and-check phải atomic với việc nhận packet/handoff theo phạm vi prototype.

Nếu recommendation vẫn eligible nhưng không còn top sau một event, phải phân biệt `SUPERSEDED_BY_BETTER_ACTION` với `REVOKED_BY_HARD_RULE`. Nếu output không đổi về nghĩa, không sinh một recommendation mới mỗi portal login. Dùng semantic decision key/coalescing; frequency cap đếm đơn vị contact/exposure đã định nghĩa, không đếm tùy tiện số lần engine chạy.

Holdout cố định 10% là thiết kế mới hợp lý nhưng cần:

- Log **shadow best NBA** đầy đủ cho mọi customer để đáp ứng expected output/jury; tách suppression giao tiếp do experiment.
- Assignment bền, seed/version rõ; không đổi theo mỗi lần replay.
- Không giữ lại service bắt buộc để làm control. Chỉ suppress marketing theo experiment scope.
- Đừng hứa hash chia 10% sẽ ra đúng 75/750 nếu chưa kiểm; nếu cần exact allocation thì stratified/exact assignment phải được định nghĩa.

### 5.8 Candidate/held rules phải biết loại action và mức chắc của fact

**Dòng 168–169, 180, 194.** Một cổng “đã có sản phẩm → loại” cho mọi action sẽ loại nhầm retention/upgrade/add-on. Mỗi action cần preconditions riêng: requires-held, requires-not-held, tariff-specific, device-specific, upgrade target và các dữ kiện chưa biết.

Ví dụ: P-MO-02 cần active mobile và repeated-limit signal; P-EN-02 cần contract/price-guarantee condition; P-AS-01 cần không active Autostrom; P-SL-02 cần HEMS + battery. Không coi thiếu internet holdings là bằng chứng phủ sóng/sẵn sàng hợp đồng internet; catalog cố ý nói không có internet holdings trong mock.

P-SV-01 cần một issue/nhu cầu service còn có thể xử lý. `clv_service_impact_eur < 0` hoặc historical handling cost không tự chứng minh có một case đang mở để fix. Không hoàn lại chi phí quá khứ trong ledger; nếu mô hình lấy past service cost làm proxy cho future cost, mức giảm dự kiến phải là assumption được chốt. Không vừa cộng lại toàn bộ service-impact vừa giảm đúng các driver đã tạo nó.

Gas deregistration được đề cho làm heat-pump trigger, nên dùng làm candidate signal là đúng challenge. Nhưng nó không tự chứng minh installation, meter eligibility hoặc ngày cung cấp. Tách `inferred_interest` với `confirmed_eligibility`; scope prototype có thể là recommendation/consultation, không personalized price/contract promise.

Ticket ID lạ không được tùy ý merge vào ticket bất kỳ cùng customer. `TK-open-complaint` không tồn tại trong snapshot; lưu orphan/update-pending, conservative customer-level complaint flag có provenance nếu cần, rồi resolve bằng mapping rõ ràng. Không sửa lịch sử ticket thật chỉ để join thành công.

## 6. Ba ví dụ demo: cần viết lại đúng theo timeline

### 6.1 MG-100009: vẫn là demo tốt nhất, nhưng lý do hiện tại sai

| Dữ kiện kiểm được | Hệ quả |
|---|---|
| Snapshot có Autostrom, không energy; CLV=403, margin=200,11, cost-to-serve=37,50, churn=.34 | Baseline hợp lệ để giải thích |
| Drivers gồm **2 tickets in 12m + 3 failed charges in 30d** | Không chỉ có driver failed charges; không cộng lại threshold sau failure thứ tư |
| Hai tickets cũ đều closed; ticket gần nhất đóng 30/09 16:15 | 17:22 ngày 01/10 chưa được nói snapshot đang có open complaint |
| Newsletter/email/phone/SMS không granted; **portal_app_personalisation và profiling đều granted**, portal account và app đều có | Không có căn cứ nói “không còn kênh marketing nào” nếu portal/app được map như thiết kế |
| Failure thứ tư 17:22, nạp 17:22:23; ticket mới 17:25, nạp 17:25:15; agent dismisses 17:27:40; transcript nạp 17:38:10 | Không được dùng “agent đang gọi”, “customer_upset” hoặc transcript ở màn 17:22 trước khi sự kiện đó tới |

Trong snapshot `service_nba_feedback` cũ của MG-100009, agent **accepted**, khách declined. Cảnh agent dismisses vì upset là event **01/10 17:27:40**, không phải cùng observation đó.

Quan trọng: không tự có định lý “sales trong mọi service case luôn ΔCLV âm”. Theo catalog additive effect P-EN-01, trước khi thêm một penalty không được nguồn định nghĩa, CLV model từ **402,9649** lên **719,3286** nếu accept. Với p=.034 minh họa và contact cost=0, expected gain ≈**+10,76 €**. Đây là phản ví dụ đại số, không estimate thật cho khách.

Service vẫn có thể thắng vì modeled expected benefit lớn hơn. Chỉ nói sales negative khi chính assumptions/penalty/score tính ra như vậy; nếu sales bị hard-block, hiển thị `BLOCKED` và lý do. Counterfactual economic score của action bị chặn có thể để giải thích riêng, không đưa vào ranking như action được phép.

**Demo sửa:** snapshot có ba failed sessions → failure thứ tư đến → recompute service candidate → ticket/feedback/transcript lần lượt đến → cập nhật explanation → service task cho agent trong scope được phép. Không cần bịa absence of channel để làm service thắng.

### 6.2 MG-100003: phải tách hai consent events

- Profiling: occurred **10:14:00**, ingested **10:14:05**.
- Newsletter: occurred **10:14:05**, ingested **10:14:11**.

Tại 10:14:05, revoke personalized marketing theo profiling policy; không ghi newsletter consent đã đổi nếu event tương ứng chưa tới. Tại 10:14:11, newsletter gate cũng chuyển withdrawn. Log từng event và lý do. Diagram 03 hiện làm hai event trông như tới cùng thời điểm; sửa timestamp trong script demo.

### 6.3 MG-100005: newsletter cũng là kênh có thể xét

Data threshold xảy ra 18:30 nhưng tới **18:49:56**. Portal app login tới 18:52:04. Không kích hoạt từ threshold lúc 18:30 trong online replay khi engine chưa nhận được nó.

Khách có SMS, portal/app, profiling **và newsletter_email granted**; marketing_email not_given. Nếu loại newsletter vì engagement/timing/cost thì nêu đúng lý do và score, không nói thiếu mọi quyền email. Tone Du là heuristic từ customer-side wording, không vì tuổi/household/app; state được phép dùng phải được kiểm.

## 7. KG/ontology: nên giữ phần nào, không nên đặt cược vào phần nào?

**Giữ một policy/dependency graph nhỏ, khách ở tables, scoring ở code.** Đây là quyết định kiến trúc phù hợp. Không cần graph database, embedding hoặc LLM reasoner để chạy 18 catalog actions và 750 customers.

Nhưng trong folder hiện chỉ có diagram, chưa có ontology schema/JSON và validation. Con số 60–80 node là planning estimate, không là capability đã đạt. Nếu không xây được phần truy vấn/dependency thì gọi là rule configuration, không pitch đã có graph reasoning.

Minimum graph contract cần có:

- Node/edge types và ID ổn định; source pointer, predicate/operator, threshold/unit/window, approval và policy version.
- Action → eligibility predicates → channels/consent; whitelist action type cho từng exclusion; no hard-rule override.
- Feature → allowed purpose; tách raw availability, permitted use và model inference.
- Event/fact → feature → candidate/score → pending decision/message; include dependencies tới CLV/probability/expiry.
- Reference validation, orphan/unknown behavior và regression cho rule release. Một graph chỉ có các đường “signal→need→action” chưa đủ để invalidate an toàn.

**Đo giá trị KG:** policy change có tìm đúng affected decisions và reason path không? So với cùng rules bằng cấu trúc flat, không so “KG có đủ data” với “baseline thiếu data”. Với một event customer-specific, tính lại toàn customer là đủ; không hứa selective rule recomputation nếu chỉ re-evaluate cả customer. Policy/global lever đổi có thể ảnh hưởng nhiều khách, không phải chỉ customer mang event.

### Đánh giá D1–D5 về tính khác biệt

| Điểm | Giá trị thật | Không nên pitch |
|---|---|---|
| D1 replay/revocation | Mạnh nếu có timeline, bitemporal/known-state explanation, pending-card preflight và latency đo được | “Luôn đúng kể cả event chưa đến”; “chưa ai có event-driven decisioning” |
| D2 service-first | Rất phù hợp business, là case đề trực tiếp yêu cầu | Đột phá riêng hoặc mọi sales score tự âm |
| D3 reason + steer | Cần cho user/jury; tốt khi lever thực sự làm thay output | Lý do đọc được chỉ là một path đẹp không phản ánh score/constraints |
| D4 data traps | Bằng chứng technical quality nếu definitions/denominators đúng | Số “vi phạm thật” MAINGAU khi chỉ có mock/snapshot proxy |
| D5 honest Learn | Làm proposal đáng tin, tránh mất điểm | Một feature novelty riêng hoặc đã chứng minh causal impact |

Pega PCVL trong dòng 131 là mô tả đúng về sản phẩm Pega, nhưng **không phải công thức jury yêu cầu cho solution này**. Marketing priority lever không được âm thầm biến expected ΔCLV thành weighted priority rồi vẫn gọi số đó là euro. [Nguồn Pega](https://academy.pega.com/topic/action-prioritization-ai/v5).

## 8. Pipeline đề xuất sau audit

```text
0  Freeze evaluation clock + source/knowledge policy + released rule/model versions
1  Load immutable raw tables/events; retain guests/machine-open records with flags
2  Reconstruct given/strict-as-of state with explicit mode and source inconsistencies
3  Apply purpose/profiling feature-use policy
4  Generate action candidates and allowed channel/tone tuples
5  Check action-specific holdings, exclusions, frequency, channel permissions, freshness
6  Calculate CLV before/accept/reject on one consistent model basis
7  Estimate/lookup p with evidence tier; calculate expected ΔCLV per tuple
8  Rank feasible tuples, keep NO_ACTION=0; log shadow winner and experiment suppression
9  Render German approved-template content + one-line reason from actual components
10 Human review bound to customer/policy/model/content revision
11 Fresh per-customer preflight → export preview; no autonomous sending

On event arrival in ingested_at order:
  dedup → keyed event/effective-time update → recompute affected customer
  → unchanged / superseded / revoked classification → stale packet blocked → log.

On policy/model/clock change:
  identify broader affected population → re-evaluate → re-review as required.
```

One-line reason cần user đọc được: ví dụ “4 charging failures → service follow-up; estimated ΔCLV €X under service-success assumption Y; sales alternative blocked by rule Z / scored lower by €D.” Có thể rút gọn trên card, mở drawer xem components. Không điền X/Y/Z trước khi code tính và policy xác nhận.

## 9. Scope tốt nhất cho năm người và tiêu chí chứng minh

### 9.1 Phạm vi nên chốt

Một backend tất định, ba view dùng cùng state: recommendation list, marketing approval/steering, customer detail 360. Tái sử dụng card/reason/score breakdown, không làm ba UI nền tảng riêng. Bắt đầu rules + fixed probability version + templates; không online learning.

Replay xử lý toàn bộ **635 unique events**, kể cả arrivals tới 03/10; các event không hỗ trợ đầy đủ payload vẫn được log `UNSUPPORTED/PARTIAL`, không âm thầm bỏ qua rồi gọi full coverage. Không cần mô phỏng mọi CDR field nếu goal chỉ cập nhật feature đủ cho decision; phải nói scope.

Scorer có đúng action types cho catalog 18 dòng; rulebook ghi catalog coverage/gaps. Nếu chỉ triển khai một subset, hiển thị subset và hạn chế so sánh “best”; hidden references có thể dùng actions khác.

Một customer chạy xuyên load → score → reason → review/export sớm. Sau đó mở rộng 750, stream, batch invalidation. Chọn deep dive B không có nghĩa bỏ Customer 360 hoặc Marketing levers — chúng là core deliverables.

### 9.2 Phân công nên điều chỉnh

| Owner | Trách nhiệm và bằng chứng |
|---|---|
| Backend/data | Two/effective clocks, dedup, snapshot modes, revision/persistence, queue/preflight; event replay same inputs same final state |
| Domain/policy | Channel map, action-specific holdings/exclusions, purposes, graph/schema release; cases độc lập kiểm source |
| Engine/evaluation | CLV functions + tuple ranking + probability tiers + all-customer invariants; report có numerator/denominator |
| AI/content | German templates, customer-side tone, concise explanation formatting; timeout fallback; hỗ trợ test/label, không dành cả người cho LLM generation |
| Frontend/demo | Ba views chung component, timeline and revoked list, lever before/after, reset/video/pitch |

Domain và Engine cùng gán expected; Backend không tự “sửa” source semantics. AI role có thể hỗ trợ QA/integration vì template/tone hẹp hơn một người code liên tục cả ngày. Không xây theo từng tầng hoàn tất tuần tự; tích hợp một vertical slice trước rồi mở rộng.

### 9.3 Test có ý nghĩa phải chạy trên implementation sau này

| Test | Điều cần assert |
|---|---|
| 750 customers at fixed clock | Có decision/no-action reason cho mọi khách, feasible tuple winner tối đa theo score đã công bố |
| Consent/profiling | Không có personalized marketing tuple khi không permitted; non-personalized/service fallback đúng policy |
| Exclusions | Block đúng action/content types; không blanket-block service hoặc giữ chân trái policy chưa được chốt |
| MG-100003 | Từng event 10:14:05/10:14:11 làm state và pending card đổi đúng; cached card không export |
| MG-100009 | Timeline không dùng future ticket/transcript; service score có probability/cost basis, không invent negative sale |
| MG-100005 | Candidate mobile hợp lệ, kênh có newsletter alternative; threshold chưa tới không được dùng |
| Late cancellation | Pending invalidated sau arrival; retrospective exposures ghi riêng; không sửa delivery log quá khứ |
| Idempotency | Replay duplicate và replay lại cùng event không tăng feature/cost/contact hoặc sinh queue item lặp |
| Ordering | Hindsight vs online mode rõ; out-of-order field update không rollback fact mới hơn hay bỏ nhầm fact khác |
| Snapshot traps | 79 CDR/two future resolutions được xử lý theo mode công bố; không âm thầm dùng future info |
| Model types | One-off một lần; retention driver đúng; service/no-action khác; reject cost đúng; no churn-driver double counting |
| Human review/lever | Stale batch item blocked; hard guard không override; ranking changes có policy version/reason |

“0 violations” chỉ báo trên **tested policy, mapping, source mode, customers và decision checkpoints**. Đo cả coverage/no-action rate; chặn mọi output để đạt zero không giải đúng challenge.

Baseline nên là static snapshot engine với **cùng score và cùng rules**, đối chiếu event-aware/preflight engine. Khi đó cải thiện do freshness có thể quy rõ hơn. Legacy rules trong mock vẫn là baseline business tham khảo, nhưng không phải đối chứng duy nhất nếu có nhiều lỗi consent đã cài sẵn.

## 10. Kiến trúc Databricks/MCP: đủ một slide nhưng ghi đúng trạng thái

Ý tưởng Delta/Unity Catalog + curated customer state + decision service + dashboard + governed tool access là hợp lý. Tách streaming update/revocation khỏi đường agent gọi MCP. MCP là tool/data access; nó không tự tạo freshness, xử lý event ordering hoặc bảo đảm race-free approval.

Dòng 259 “managed MCP server hiện vẫn Public Preview” quá tổng quát ở ngày 26/10. Tài liệu AWS mới phân biệt Databricks-provided MCPs qua Unity Gateway và **Unity Catalog functions MCP legacy endpoint**. Có service GA, có thành phần Beta; không gộp chung trạng thái. Cập nhật slide theo workspace/cloud được dùng, không phải thêm công việc migrate production trong hackathon. [Databricks-provided MCPs, cập nhật 21/10](https://docs.databricks.com/aws/en/agents/mcp-tools/built-in-mcp-services), [UC functions MCP legacy, cập nhật 07/10](https://docs.databricks.com/aws/en/agents/mcp-tools/uc-functions).

Đề chỉ yêu cầu architecture concept. Một prototype local có adapter/mock label và đường triển khai rõ vẫn khớp đề; không giả Databricks integration đã chạy.

## 11. Pitch nên tập trung vào đâu?

Với rubric 75% nằm ở technical/feasibility/impact, ưu tiên correctness và thao tác thật trước một ontology nhiều thuật ngữ. Tên gọi có thể giữ **MAINGAU NBA**, signature là **recommendation có dependency, biết tự mất hiệu lực và marketer sửa được**.

Khung 8 phút:

1. 0:00–0:40: một customer, một quyết định model-based CLV, problem đúng lời challenge.
2. 0:40–2:10: customer card có feasible alternatives, score components, channel/tone/reason.
3. 2:10–3:40: MG-100009 service-first đúng theo dữ kiện đã biết.
4. 3:40–5:00: MG-100003 từng consent arrival làm recommendation mất hiệu lực; thử dùng card cũ và bị block.
5. 5:00–6:00: marketing lever/policy change → preview trước/sau, approve; Customer 360 dùng cùng decision state.
6. 6:00–6:45: một late event, known-time vs occurred-time, limitations rõ.
7. 6:45–7:20: một slide target architecture Databricks/MCP.
8. 7:20–8:00: x/y tests thực, Learn concept, pilot ask.

Hook tiếng Anh có thể dùng sau khi đã build: **“A recommendation is useful only while its inputs and permissions are valid. We show what changes, why, and which pending actions must stop.”** Không dùng câu tuyệt đối “Every recommendation stays correct” khi source có thể trễ 47 giờ.

## 12. Câu hỏi ưu tiên hỏi mentor

1. “For grading, should state columns be treated as the authoritative snapshot, or should we reconstruct as-of state from timestamps? We found 79 later-received CDRs and a complaint marked closed after the snapshot date.”
2. “Can portal_popup and app_push both use portal_app_personalisation? How should service-agent suggestions be treated when outbound marketing permission is absent?”
3. “What is the approved fallback when profiling consent is not granted or is withdrawn?”
4. “Do open non-complaint service cases also block sales, or only the exclusions on slide 12? Does pending cancellation block retention content?”
5. “For P-SV-01, what success/acceptance probability and cost treatment should we assume? Which cost and churn drivers are removed?”
6. “Should a new business line add €12 cost-to-serve, and do catalog churn effects already cover the bundle effect?”
7. “What are the contact caps and the expected semantics of holdout for reference customer recommendations versus delivery suppression?”

Ghi lại câu trả lời thành policy/model version; không đợi có toàn bộ câu trả lời mới làm persistence và ba view. Với phần chưa chốt, giữ assumption có nhãn, fail closed cho permission/hard rules và giảm claim tương ứng.

## 13. Những sửa cụ thể vào file pipeline và diagrams

| Vị trí | Sửa |
|---|---|
| Dòng 19, 141, 147 | Giới hạn lời hứa theo state đã biết; thay test end-of-stream bằng per-transition/preflight validity |
| Dòng 40/191 | Phân biệt count slide với file thực 23 sheets/18 registered tables |
| Dòng 45–46 | Giữ raw records; chỉ loại machine-open feature; quarantine guest/orphan có provenance |
| Dòng 55–67; diagram 01 | Feature-use policy trước personalization; channel/tone tuples trước score; hard rules + score + arbitration rõ |
| Dòng 82–95; diagram 02 | Ingestion-order replay, per-key clocks, pending-only revocation, effective date và preflight |
| Dòng 141–145 | Qualify 70/81; phân biệt 72 snapshot holders với 70 start-date checked; 55 dismissed +11 ignored |
| Dòng 168–169; diagram 04 | Preconditions theo action type; sales-content scope; service/no-action tách; approved graph package |
| Dòng 203–209; diagram 05 | Sửa MG-100009: portal/app grants, closed old tickets, timeline 17:22→17:25→17:27→17:38; không tự claim sales âm |
| Dòng 217–220; diagram 03 | Tách hai consent events và thời điểm nhận 10:14:05/10:14:11 |
| Dòng 227–230 | Mobile threshold tới 18:49:56; newsletter là candidate channel nếu policy cho phép |
| Dòng 239–245 | Thống nhất as-of clock, source-count definitions, tone heuristic và maturity của labels |
| Dòng 259 | Cập nhật MCP terminology/status từ official docs hoặc bỏ nhãn release tổng quát |
| Dòng 273 | Shadow recommendation riêng với holdout delivery; stable assignment không suppress required service |
| Dòng 287 | Vertical slice sớm; không tuần tự hoàn thiện cả data/KG rồi mới nối UI |

**Ưu tiên thực hiện:** tuple scoring + consent/purpose policy → source/as-of contract → CLV pure functions/probability assumptions → state/review/preflight → ba view + replay demonstration → baseline/invariants. Giữ graph nhỏ và Learn concept. Đây là cách làm solution hiện tại vững hơn trước jury; không cần đổi sang một idea mới.
