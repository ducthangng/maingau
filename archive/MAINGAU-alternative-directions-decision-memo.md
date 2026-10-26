# MAINGAU — những hướng đáng cân nhắc ngoài MomentPilot hiện tại

Ngày nghiên cứu: 25/10/2026. Bối cảnh: đội 5 người, AI hỗ trợ code, khoảng 27 giờ lịch từ deep dive tới pitch theo agenda đã nhận.

**Có hướng sáng tạo hơn và có thể quan trọng hơn bản proof-of-benefit hiện tại. Hai ứng viên mạnh nhất là FlexMoment và JourneyPilot.** FlexMoment chuyển từ bán sản phẩm sang khuyến khích hành vi linh hoạt có ích. JourneyPilot chuyển từ chọn một offer hôm nay sang một kế hoạch khả thi qua nhiều sản phẩm và thời điểm. BillShield là lựa chọn thứ ba nếu partner ưu tiên vấn đề billing/retention.

Đây là đánh giá hướng sản phẩm, chưa phải một pivot được dữ liệu MAINGAU xác nhận. Chưa biết rubric hoặc ý tưởng đội khác. “Ít trùng” là mục tiêu thiết kế, không phải kết quả có thể bảo đảm.

## 1. Vì sao nên xét lại câu chuyện sản phẩm?

MomentPilot đã thiết kế trước đó có nền đúng: nguồn và phép tính rõ, benefit không đếm trùng, alternative không cần mua, permission hiện tại và message có căn cứ. Nhưng phần lớn là **lõi chất lượng quyết định**. Nó chưa nhất thiết là câu chuyện hấp dẫn nhất trên sân khấu.

Có thể giữ lõi ấy bên dưới một sản phẩm giải quyết mục tiêu lớn hơn. Không cần build thêm ba app hoặc ghép mọi hướng vào một hệ thống.

Ba sự thật nghiên cứu định hướng lựa chọn:

| Dữ kiện đã kiểm tra | Nguồn | Điều có thể suy ra / điều chưa biết |
|---|---|---|
| MAINGAU tham gia Grids & Benefits, có pilot về incentive cho charging | [Trang dự án của UnternehmerTUM](https://www.unternehmertum.de/en/landingpages/grids-and-benefits) | Flexibility là lĩnh vực có liên quan thực; chưa biết đội hackathon có data và mandate của mảng đó |
| StromDynamisch có điều kiện smart meter và giá biến đổi theo thời gian; công ty nêu cả rủi ro giá | [MAINGAU StromDynamisch](https://www.maingau-energie.de/strom/stromdynamisch) | Phải xét khả năng sử dụng và sự sẵn sàng, không chỉ affinity mua |
| Có quy trình chuyển nhà cho energy/internet; Parloa đã xử lý nhiều service và tariff advice | [Forms energy](https://www.maingau-energie.de/service/formulare), [FAQ internet](https://www.maingau-energie.de/service/faq-internet), [Parloa case study](https://www.parloa.com/customers/maingau/) | Không phát minh một bot chuyển nhà nữa; khoảng trống phối hợp xuyên sản phẩm cần mentor xác nhận |

Nguồn chứng minh capability/use case tồn tại, không tự chứng minh pain còn bỏ ngỏ, quy mô thiệt hại hay ROI của đề xuất mới.

## 2. FlexMoment — chọn ưu đãi để tạo hành vi linh hoạt khả thi

**Câu hỏi sản phẩm:** “Với người này, tại thời điểm này, ưu đãi nào có thể giúp họ chuyển hành vi theo cách có lợi và thực hiện được?”

Ví dụ: người dùng có thể lùi một phiên sạc tới khung phù hợp, đổi địa điểm trong giới hạn chấp nhận hoặc cân nhắc một sản phẩm hỗ trợ linh hoạt. Hệ thống chọn trong catalog incentive được duyệt; không tự tạo discount hoặc tự điều khiển thiết bị.

### Vì sao sát MAINGAU hơn một ý tưởng chung về green energy?

Báo cáo Grids & Benefits có một slide riêng về MAINGAU Autostrom, so các mức reward và nhóm đối chứng trong khung sạc thuận lợi. Đây là bằng chứng nghiên cứu của dự án đã có, không phải kết quả đội hackathon. [Final Review, slide in số 34, PDF trang 31](https://ut-um.files.svdcdn.com/production/media/downloads/Grids-and-Benefits_Final-Review_public.pdf?dm=1770024456).

**Do đó, “gợi ý giờ rẻ” hoặc “gửi discount lúc xanh” đã quá gần việc có sẵn.** Đề xuất mới phải đi thêm vào feasibility của từng người, lựa chọn incentive trong giới hạn ngân sách và cách đo phần thay đổi hành vi thực sự tăng thêm.

### Sản phẩm hoạt động thế nào?

1. Khách khai báo nhu cầu thực: cần sẵn xe lúc nào, lượng sạc cần, khung có thể sạc và giới hạn thay đổi chấp nhận được.
2. Backend tạo các phương án khả thi từ catalog/window được partner cung cấp. Không tự có dữ liệu station availability hoặc grid capacity.
3. Loại phương án làm trễ nhu cầu, không đủ sạc, vượt budget hoặc không có permission.
4. Chọn một incentive được phép hoặc không đề xuất; hiển thị benefit, effort, giới hạn và điều kiện.
5. Soạn message theo kênh được phép và preference; ghi acceptance, redemption và hành vi quan sát nếu có nguồn dữ liệu.

**Demo:** hai người có cùng lịch sử charging nhưng deadline khác nhau. Người thứ nhất nhận một offer dịch giờ; người thứ hai không nhận vì không còn phương án đáp ứng nhu cầu. Đổi một deadline hoặc budget, recommendation thay đổi có lý do.

Đó là một offer có ý nghĩa thực tế, không chỉ một email được viết riêng.

### Điểm quan trọng hơn về chiến lược

Nếu MAINGAU có quyền triển khai/funding phù hợp, đây là cách biến customer relationship thành khả năng huy động flexibility: ích lợi cho khách, vận hành năng lượng và các bên cung cấp dịch vụ. Đây là suy luận cơ hội sản phẩm, chưa phải lợi nhuận MAINGAU được chứng minh.

Ba giá trị phải tách:

- Tiết kiệm cho người dùng.
- Lợi ích vận hành/lưới cho bên có thể nhận lợi ích đó.
- Chi phí và doanh thu MAINGAU thực sự ghi nhận theo cơ chế thương mại.

Giảm chi phí lưới không tự thành tiền MAINGAU nhận. Giá điện bán buôn thấp không đồng nghĩa lưới địa phương đang rảnh hoặc carbon thấp. Public charging có CPO/EMSP và cơ chế thanh toán riêng; không dùng giá spot để tự tính margin discount.

### AI cần làm gì?

Trích nhu cầu/giới hạn từ ngôn ngữ người dùng, hỏi fact còn thiếu và giải thích trade-off. Planner và phép tính chạy bằng code. Nếu có logs randomized đủ support mới học heterogeneous response; báo cáo aggregate công khai không đủ để tạo model uplift cá nhân.

“Chọn incentive thấp nhất vẫn làm khách đổi hành vi” là mục tiêu nghiên cứu, không phải tính năng đã biết đúng khi thiếu response data. Launch mode nên là feasibility + catalog policy + experiment proposal.

### Scope đội 5 người

- Một use case charging; một horizon ngắn; 2–3 incentive types đã duyệt.
- Vài customer profiles và một bộ window được gắn nhãn nguồn.
- Feasibility checks, budget, recommendation card, message và outcome log.
- Không xây dự báo grid, reservation, hardware control, charging network hoặc online bandit.

**Điều kiện chọn:** mentor xác nhận incentive offer nằm trong challenge; có catalog/windows dùng được; biết ai tài trợ và đo outcome thế nào. Nếu thiếu các điều kiện này, demo dễ thành simulator hấp dẫn nhưng chưa có đường triển khai.

**Pitch:** “The next best offer can be a reward for flexibility the customer can actually provide.”

## 3. JourneyPilot — chọn một con đường khả thi, không chỉ một offer

**Câu hỏi sản phẩm:** “Để người này đạt mục tiêu trong vài tuần tới, nên làm những việc gì, theo thứ tự nào, và offer nào có ích ở từng bước?”

Chọn một sự kiện duy nhất để build, ưu tiên chuyển nhà nếu partner xác nhận đó là pain xuyên sản phẩm. Kết hợp tối đa energy và internet; các nhóm sản phẩm khác để sau.

### Phần nào đã có, phần nào là đề xuất mới?

MAINGAU đã có forms và service hỗ trợ chuyển nhà. FAQ internet còn nêu cần xét availability tại địa chỉ mới, lead time và phí phù hợp. [FAQ Internet](https://www.maingau-energie.de/service/faq-internet).

**“AI phát hiện khách sắp chuyển nhà rồi chào internet” chưa phải điểm mới.** Đề xuất ở đây là một plan có dependency, dates, missing facts và trạng thái, được tính lại khi đầu vào đổi; chưa biết MAINGAU đã có orchestration tương đương hay chưa.

### Ví dụ demo

Input synthetic: khách chuyển nhà ngày 15/11, muốn có kết nối cho công việc từ ngày 16/11, đang có energy và một internet contract. Availability ở địa chỉ mới chưa được xác nhận.

Plan không hứa một offer ngay:

1. Xác nhận địa chỉ, phạm vi hợp đồng và những dữ kiện cần để kiểm tra dịch vụ.
2. Đưa bước kiểm availability/khả năng chuyển hợp đồng lên trước recommendation phụ thuộc nó.
3. So các phương án đủ điều kiện theo thời gian, phí, existing benefits và nhu cầu khách đã khai báo.
4. Chọn một offer có thể thực hiện cùng channel/tone thích hợp; phần chưa xác nhận giữ pending.
5. Xuất action packet cho workflow được ủy quyền, gồm chủ việc, dữ liệu cần, ngày dự kiến và blockers.

**Khoảnh khắc demo:** đổi ngày chuyển nhà sớm hơn hoặc nhận kết quả “fiber unavailable”. Hệ thống rút recommendation cũ, đánh dấu dependent tasks cần xem lại và đề xuất phương án khác trong catalog đã duyệt. Không chỉ sửa câu trả lời chatbot.

Không tự bảo đảm ngày cung cấp dịch vụ, downtime bằng 0 hoặc quyền chuyển hợp đồng. Một plan còn pending không được mang nhãn ready-to-execute.

### Vì sao có thể quan trọng hơn một recommender mỗi ngày?

Giả thuyết: khách mua thêm hoặc ở lại khi họ hoàn tất được một việc có giá trị, không chỉ khi được nhắm đúng một thông điệp. Một plan có thể giảm việc trao đổi lặp và offer chưa đủ điều kiện; retention/cross-sell cần đo bằng pilot.

Tính mới tương đối nằm ở **sequence và re-planning xuyên sản phẩm**, không phải có timeline UI. Nếu chỉ thêm một checklist cố định vào MomentPilot thì chưa đủ khác biệt.

### AI và planner

AI trích goal, dates, preferences và facts từ một service summary; người dùng xác nhận dữ kiện quyết định. Backend dùng action templates với `requires`, `produces`, thời gian, costs và source/policy version để lập plan có giới hạn.

Không cần autonomous agent tổng quát. Chỉ cần 4–6 action templates, 2 product families, ba tình huống thay đổi và một export lưu được. Mỗi việc có trạng thái và evidence, không chỉ câu “AI đề xuất”.

### Scope và kiểm chứng

- Một input summary + structured contracts.
- Một goal, một plan 3–5 bước, một offer hợp lệ trong plan.
- Cost/benefit engine hiện tại được tái sử dụng.
- Một re-plan do date đổi, một do eligibility/availability đổi.
- Permission và source revision được kiểm trước handoff.

Baseline mạnh: current agent checklist hoặc playbook chuyển nhà nếu được cung cấp. Đo plan validity, dependency omissions, reviewer corrections, completion time và số lần cần hỏi thêm; chưa có pilot thì không báo đã giảm churn.

**Điều kiện chọn:** mentor xác nhận pain là coordination; không có journey automation đã giải quyết đầy đủ; có action catalog/policy và dữ kiện đủ để kiểm plan.

**Pitch:** “The best next offer is the next feasible step in the customer’s plan.”

## 4. BillShield — xử lý vấn đề hóa đơn trước khi khách phải tìm tới MAINGAU

**Câu hỏi sản phẩm:** “Từ dữ kiện tiêu thụ, tariff và payments đã có, việc nào nên làm trước khi khách gặp một khoản quyết toán bất ngờ?”

Parloa mô tả MAINGAU có nhu cầu service theo mùa quanh meter readings và installment adjustments; công ty cũng đã có self-service cho việc này. Phần mới phải là trigger chủ động có evidence và action đúng, không thêm chatbot xử lý khi khách đã gọi. [Parloa case study](https://www.parloa.com/customers/maingau/), [FAQ energy](https://www.maingau-energie.de/service/faq-strom-und-gas).

Ví dụ: xác minh reading bất thường → giải thích vì sao projection đổi → chuẩn bị adjustment hoặc một approved offer phù hợp → handoff đúng purpose/channel. Không gọi mọi khoản quyết toán cao là lỗi hoặc bad tariff.

Phải phân biệt thay đổi consumption cost, thay đổi tiền trả trước và giảm thực chi. **Điều chỉnh Abschlag không tự làm điện rẻ hơn.** Nếu thiếu readings đủ tin cậy hoặc tariff thì yêu cầu xác minh, không tạo saving projection giả.

### Điểm mạnh và điểm yếu

- Có thể quan trọng nếu billing surprise là pain được partner xác nhận; chưa có bằng chứng đây là nguyên nhân churn lớn nhất của MAINGAU.
- Kỹ thuật dễ build hơn FlexMoment nếu có meter/tariff/payment data.
- Novelty vừa phải: proactive care/churn prevention là hướng quen; cần một case và workflow rất cụ thể để nổi bật.
- Có nguy cơ lệch challenge sang customer service. Chỉ chọn khi mentor chấp nhận action/service là output phù hợp và vẫn có selection offer/channel/tone khi có căn cứ.

Không suy luận hoàn cảnh tài chính, vulnerability hoặc khả năng trả nợ từ usage để nhắm thuyết phục. Cần scope dữ liệu và purpose phù hợp.

**Pitch:** “Act on the bill the customer is about to face, before it becomes another support call.”

## 5. Hướng thứ tư: DecisionLab — quan trọng nhưng không nên đứng một mình

AI tạo các test cases khó từ catalog/policy và chạy **decision engine thực sự được build**: benefit đã có, expiry, dates, ambiguous facts, withdrawal, conflicting accounts. Dashboard chỉ ra policy change làm invalid recommendation ở đâu.

Đây là phần kiểm tra chất lượng decisioning, không phải simulator biết khách nào sẽ mua. Synthetic chỉ chứng minh cơ chế, không dự báo conversion hay ROI.

Nó có thể là một signature feature tốt cho JourneyPilot/MomentPilot, nhưng nếu làm app riêng sẽ xa yêu cầu “find next offer” và dễ trở thành một QA tool chung. Không chia đội thành một nhánh build sản phẩm và một nhánh build nền tảng test tổng quát.

## 6. So sánh trước khi biết dữ liệu ngày thi

Các mức là đánh giá của người thiết kế, chưa là điểm jury hoặc xác suất thắng.

| Hướng | Khác biệt tiềm năng | Tầm quan trọng có thể đạt | Khả thi trong quỹ giờ | Rủi ro lớn nhất |
|---|---|---|---|---|
| MomentPilot hiện tại | Vừa; domain proof sâu | Correct offers, trust và effort | Cao khi có catalog/holdings | Calculator/workbench thiếu câu chuyện lớn |
| **JourneyPilot** | Cao nếu plan và re-plan có logic thật | Hoàn tất hành trình, phối hợp dịch vụ và cross-sell | Khá cao trong 1 event/2 families | MAINGAU đã có orchestration tương đương; drift sang service |
| **FlexMoment** | Cao nếu có feasibility và incentive evidence | Hành vi linh hoạt, energy services và reward economics | Trung bình, phụ thuộc data/mandate | Funding, grid signals, outcomes và capability đã có |
| BillShield | Vừa | Proactive billing care/retention nếu pain được xác nhận | Khá cao với data thích hợp | Prediction thiếu evidence; challenge fit |
| DecisionLab riêng | Vừa | Reliability của policy/automation | Khá cao trong scope nhỏ | Không trực tiếp giải next-offer challenge |

## 7. Tôi sẽ chọn gì cho đội?

**Nếu phải chọn ngay với thông tin hiện có: JourneyPilot là lựa chọn mặc định tốt hơn về cân bằng sản phẩm, demo và khả năng build.** Giữ MomentPilot làm lõi kiểm giá trị, thêm một planner hẹp và re-planning thật. Không ghép FlexMoment/BillShield cùng lúc.

**Nếu mentor xác nhận được incentive catalog, data và commercial ownership: ưu tiên FlexMoment để đặt cược sáng tạo hơn.** Đây là cơ hội chiến lược có bằng chứng hoạt động nghiên cứu thật, nhưng không nên chọn chỉ vì nghe “energy transition” hấp dẫn.

**Nếu MAINGAU nói billing/service retention là pain chính và đưa dữ liệu tương ứng: BillShield có thể quan trọng hơn cả hai**, dù điểm mới không tự cao hơn. Business pain thực có thể quan trọng hơn độ lạ của tên idea.

### Ba câu quyết định ngay sau deep dive

1. “Which matters more here: cross-selling another contract, completing a customer transition, preventing avoidable service issues, or encouraging flexible energy behaviour?”
2. “What part is not already solved by your current Kraken/Parloa workflows?”
3. “Which data and approved actions can we use to demonstrate one completed decision today?”

Quyết định theo câu trả lời và một case thực, không theo độ nhiều tính năng. Đội cần một sản phẩm có thể chứng minh khác biệt trong vài phút.

## 8. Bằng chứng cần có trong demo

| Hướng | Một chứng minh bắt buộc | Một claim chưa được nói khi chưa đo |
|---|---|---|
| JourneyPilot | Đổi constraint → plan/offer phụ thuộc đổi đúng, lịch sử giữ lại | Đã giảm churn hoặc tự hoàn tất mọi hợp đồng |
| FlexMoment | Deadline/window/budget → offer feasible hoặc bị loại đúng | Biết uplift cá nhân hoặc minimum effective reward từ aggregate report |
| BillShield | Input/evidence khác → projection/action đổi đúng, phân biệt payments/costs | Mọi adjustment giảm chi phí hoặc ngăn churn |
| MomentPilot | Benefit có sẵn → không được ghi công cho new offer | Sum projected customer savings = company profit |

Nguồn, fixtures, policy, cached/live output và quyền thực thi phải được gắn nhãn. Tất cả action thay đổi hợp đồng/gửi message vẫn cần workflow đã được ủy quyền; demo có thể dừng ở review/export.

## 9. Tài liệu liên quan

- [Blueprint MomentPilot đã có](MAINGAU-examiner-review-va-product-blueprint.md).
- [Brief đội 5 người](MomentPilot-team-execution-brief.md).
- [Nghiên cứu gốc MAINGAU trong báo cáo chung](../../ITSG/Futury%20Build%20Days%202026%20%E2%80%93%20Ba%CC%81o%20ca%CC%81o%20phu%CC%9Bo%CC%9Bng%20a%CC%81n%20sa%CC%81ng%20ta%CC%A3o%20cho%20ITSG%20%26%20MAINGAU.md), dùng để xét hướng khác; các claim cũ không mặc định đã được xác minh.
- [Bản công khai Grids & Benefits, lưu offline](../references/Grids-and-Benefits-Final-Review-2026.pdf), 44 trang PDF; số slide in trên tài liệu có khác page index. Tham chiếu MAINGAU ở slide 34 tương ứng trang PDF 31.

Tài liệu này bổ sung các lựa chọn chiến lược; không khẳng định blueprint trước đã sai toàn bộ và không thay đổi dữ liệu hoặc sản phẩm đang có.
