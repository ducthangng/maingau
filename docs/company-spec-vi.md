# Spec gốc (đã consult với MAINGAU) — read-only

Bản gốc tiếng Việt, giữ nguyên văn để đối chiếu. Bản tiếng Anh dùng để build nằm trong [README.md](../README.md) §4.

```text
# Bối cảnh
Prototype Next Best Action cho MAINGAU Energie (Build Days). Dữ liệu: maingau_nba_mockdata.xlsx,
750 khách hàng (150 khách chỉ dùng Autostrom), 15 bảng nguồn nối qua customer_id.
Snapshot: 2026-09-30 23:59. Event stream (JSONL) bắt đầu từ 2026-10-01.
Các sheet tham chiếu: sources (nguồn và độ trễ), columns (giải thích cột),
clv_method + value_assumptions (cách định giá action), product_catalog (18 offer).

# Nhiệm vụ
Màn hình cho từng khách hàng, gồm 2 card đặt cạnh nhau:
- Card trái: Customer Profile, trả lời "khách này là ai" và "họ đang thay đổi thế nào"
- Card phải: Next Best Action, trả lời "nên làm gì" và "vì sao"
Người dùng: [marketing / service agent / cả hai]. Họ phải hiểu khách hàng trong ~30 giây.
Nguyên tắc: mỗi con số trên card có tooltip ghi bảng.cột nguồn và thời điểm cập nhật
(lấy refresh/latency từ sheet sources).

═══════════════════════════════════════════
# CARD TRÁI – CUSTOMER PROFILE
═══════════════════════════════════════════

## A. Khách hàng là ai

A1. Header
- customer_id, nhóm tuổi (suy từ customer_master.birth_year, hiển thị dạng "50–59"),
  city, household_size
- Thời gian gắn bó: tính từ customer_master.customer_since
- Mức độ digital: portal_account, app_installed, preferred_contact_language
- Xưng hô (Du/Sie), suy ra theo thứ tự ưu tiên:
  1) service_interactions.message_text và call_transcripts.transcript
     ("Hi", "danke dir", "tschüss" → Du; "Sehr geehrte", "Mit freundlichen Grüßen" → Sie)
  2) newsletter_performance: khách có click hay không, theo newsletter_campaigns.tonality
  3) Không có tín hiệu → mặc định Sie, ghi rõ là mặc định
  Luôn hiển thị bằng chứng, ví dụ: "Du – 2/2 tin nhắn dùng 'du', gần nhất 2026-08-14"

A2. Giá trị và rủi ro (customer_value)
- clv_eur, annual_margin_eur, cost_to_serve_12m_eur, active_business_lines
- churn_prob_12m kèm churn_drivers (hiển thị dạng tag)
- clv_service_impact_eur: "Sự cố service đang làm mất €X CLV"
- Percentile so với toàn bộ 750 khách, hoặc so với nhóm cùng tổ hợp sản phẩm

A3. Sản phẩm đang dùng trên 5 mảng (dạng lưới; ô trống = cơ hội, tô màu nhạt)
- Energy (energy_contracts): commodity, tariff, status, annual_consumption_kwh,
  price_guarantee_until (đếm ngược số ngày), meter_type (smart_meter_imsys?),
  feed_in_meter (khách có PV), payment_method
- Autostrom (autostrom_contracts + charge_sessions): status, car_brand/model,
  battery_kwh, charge_cards, app_user; kWh/tháng; tỷ lệ AC/DC
- Mobile (mobile_contracts): plan, data_volume_gb so với avg_data_used_gb_3m,
  data_limit_reached_3m, sim_count so với household_size, min_term_end
- Shop (shop_orders, chỉ đơn có customer_id): các đơn gần nhất, product_category,
  order_status (đơn returned/cancelled không tính là đang sở hữu)
- Smart Living (hems_devices): danh sách device_type, connection_status;
  gateway offline thì cảnh báo
- Internet: không có dữ liệu sở hữu, chỉ là offer tiềm năng

A4. Consent và Exclusion (đèn giao thông; đặt ở đầu card, không giấu)
- Consent (consent_status), 6 loại, mỗi loại hiển thị status + updated_at + source:
  newsletter_email, marketing_email, marketing_phone, marketing_sms,
  portal_app_personalisation, profiling_analytics
- Bảng map kênh → consent cần có:
  newsletter_email → newsletter_email (đã DOI)  | email → marketing_email
  outbound_call → marketing_phone               | sms → marketing_sms
  portal_popup / app_push → portal_app_personalisation (+ có portal/app)
  Mọi cá nhân hóa → profiling_analytics
- Khách đã unsubscribe trong newsletter_performance thì coi như withdrawn,
  kể cả khi consent_status chưa cập nhật
- Exclusion đang có hiệu lực:
  energy_contracts.dunning_level ≥ 1; status = cancellation_pending;
  service_interactions có status = open (đặc biệt category = complaint);
  autostrom_contracts.status = cancelled

A5. 2–3 điểm nổi bật
Chỉ chọn những điểm thực sự khác thường so với population. Ví dụ:
"Top 10% CLV", "Sạc DC gấp 3 lần trung bình", "Có PV nhưng chưa có HEMS",
"Chạm giới hạn data 3/3 tháng". Mỗi điểm phải ghi rõ dựa trên cột nào.

## B. Khách hàng thay đổi thế nào

B1. Timeline sự kiện (dọc, mới nhất ở trên, 12 tháng + các mốc tương lai)
- Hợp đồng: start_date, cancellation_received_at, meter_deregistered_at,
  autostrom cancelled_at
- Mốc sắp tới: price_guarantee_until, mobile min_term_end
- Service: service_interactions.created_at, category, status, csat_1to5,
  repeat_of_ticket_id (đánh dấu là "liên hệ lặp lại")
- Mua hàng: shop_orders.order_created_at, product_name, order_status
- Consent: consent_status.updated_at khi status đổi
- Marketing đã gửi: nba_action_history (offer, channel, response), bỏ qua control_group
Mỗi dòng có icon theo mảng kinh doanh và tag nguồn dữ liệu.

B2. Xu hướng (mini chart, ghi rõ khoảng thời gian thật của data)
- Sạc xe (charge_sessions, 06–09/2026): kWh/tháng, số session failed theo
  failure_reason. Đánh dấu mốc giảm giá AC ngày 01/07/2026. Ghi chú "dữ liệu roaming
  có thể trễ đến 72h" (cdr_received_at)
- Portal/app (portal_sessions, 07–09/2026): số session/tháng, số lần xem trang
  offers / tariff / consumption (tách từ pages_viewed)
- Newsletter (newsletter_performance, 01–09/2026): số mail mở và click thật
  (loại open_client_class = apple_mpp_prefetch), click_target theo chủ đề
- Service (12 tháng): số ticket/quý, CSAT gần nhất, tổng goodwill_eur
- Mobile: chỉ có số tổng hợp 3 tháng; hiển thị dạng thanh usage/limit, không vẽ trend
- HEMS (hems_telemetry_daily, chỉ 09/2026): self_consumption_rate, grid_export,
  heat_pump_kwh, ev_charging_kwh. Các ngày bị thiếu = thiết bị offline
- Không vẽ trend CLV vì customer_value chỉ là snapshot. Ghi rõ điều này trên card

B3. Lịch sử liên hệ và mức độ "mệt mỏi" (fatigue)
- Số lần liên hệ trong 30/90 ngày (nba_action_history, delivery_status = delivered),
  tỷ lệ phản hồi, offer bị bỏ qua nhiều lần
- Đánh dấu action cũ có consent_checked = False ("legacy engine đã gửi khi chưa
  kiểm tra consent")
- Nếu có: service_nba_feedback (agent_action, customer_reaction = annoyed)

B4. Signals (cầu nối sang card phải)
Mỗi signal gồm: id, mô tả, ngày, bảng nguồn, độ mạnh (strong/medium/weak),
và các offer mà nó kích hoạt. Ví dụ:
- S1 Gas meter deregistered 2026-08-03 (energy_contracts) – strong → P-EN-03, P-SL-01
- S2 3 lần sạc failed trong 30 ngày (charge_sessions) – strong → P-SV-01
- S3 Đã mua Wallbox nhưng chưa có Autostrom (shop_orders) – strong → P-AS-01, P-SL-03
- S4 Price guarantee hết hạn trong 90 ngày (energy_contracts) – strong → P-EN-02
- S5 Chạm limit data ≥ 2/3 tháng (mobile_contracts) – medium → P-MO-02
- S6 household_size > sim_count (customer_master + mobile) – weak → P-MO-03
- S7 feed_in_meter hoặc có pv_inverter nhưng chưa có hems_gateway – medium → P-SL-01
- S8 HEMS + home_battery / wallbox – medium → P-SL-02 / P-SL-03
- S9 Smart meter + (HEMS | EV | heat pump) – medium → P-EN-05
- S10 Click thật vào nội dung heat pump/PV/e-mobility – weak, dùng để củng cố signal khác
- S11 Khách chỉ dùng Autostrom, chưa có hợp đồng điện – medium → P-EN-01
Bỏ event trùng (theo event_id + timestamp) trước khi tạo signal.

═══════════════════════════════════════════
# CARD PHẢI – NEXT BEST ACTION
═══════════════════════════════════════════

C1. Action đứng đầu
- Offer (product_id + product_name, action_type), channel, tone (Du/Sie),
  thời điểm đề xuất gửi
- ΔCLV kỳ vọng (€), độ tin cậy (cao/trung bình/thấp)
- Trạng thái: proposed → approved / overridden (không tự động gửi)

C2. Lý do một dòng, ngôn ngữ đời thường, có tham chiếu signal:
"Gas meter đã hủy 8 tuần trước [S1] → nhiều khả năng đã lắp heat pump →
StromWärme qua email, +€42 CLV kỳ vọng"

C3. Chuỗi suy luận (drill-down, đường đi trong KG)
Customer –EMITTED→ Signal S1 –INDICATES→ Need "heat pump" –ADDRESSED_BY→ P-EN-03
–DELIVERED_VIA→ marketing_email –REQUIRES→ Consent(marketing_email = granted ✓)
Click vào mỗi node để quay lại đúng dòng tương ứng trong card trái.

C4. Cách tính giá trị (theo clv_method, tham số lấy từ value_assumptions)
ΔCLV = p_accept × (CLV_after_accept − CLV_now)
     + (1 − p_accept) × (CLV_after_reject − CLV_now) − contact_cost
- CLV_now = customer_value.clv_eur
- CLV_after_accept: cộng annual_margin_if_bought_eur, churn + churn_effect_if_bought
  (offer shop: chỉ cộng margin một lần). P-EN-02: bỏ churn driver "price guarantee".
  P-SV-01: bỏ các churn driver liên quan service, trừ service_resolution_cost_eur
- CLV_after_reject = CLV_now, TRỪ KHI liên hệ bán hàng lúc khách đang có
  open complaint / dunning: churn + contact_during_service_case (0.05)
- p_accept: conversion rate theo offer × channel × tone từ nba_action_history,
  trừ đi baseline của control group (uplift). Luôn hiển thị n mẫu;
  n < 30 thì gắn nhãn "độ tin cậy thấp" và dùng rate của cấp cha (offer × channel)
- contact_cost: email 0.01 / sms 0.08 / popup 0 / call 6 €
Hiển thị dạng bảng nhỏ để marketer tự kiểm tra lại phép tính.

C5. Checklist đã kiểm tra (mỗi dòng ✓ hoặc ✗ kèm nguồn)
Consent cho kênh ✓ | Profiling consent ✓ | Không có exclusion ✓ |
Khách chưa sở hữu sản phẩm ✓ | Không vượt giới hạn liên hệ (≤ [N] lần/30 ngày) ✓ |
Dữ liệu đủ mới ✓ (vd: đánh dấu nếu CDR roaming chưa về đủ)

C6. Phương án khác
- 2–3 action dự phòng kèm ΔCLV, và lý do chúng xếp sau
- Action bị chặn: offer + rule chặn (ví dụ "P-MO-01 bị chặn: marketing_phone
  withdrawn 2025-03-02"; "Mọi sales offer bị chặn: dunning_level = 2")
- So sánh với rule_engine_v1 (rule_id gần nhất trong nba_action_history):
  "Hệ thống cũ sẽ gửi R-SHOP-GENERIC, ΔCLV €−0.4"

C7. Xem trước nội dung gửi khách (tiếng Đức, đúng Du/Sie)
- Subject + 2–3 câu nội dung. Không cá nhân hóa giá, không tạo khẩn cấp giả.
  Với service fix: nội dung xin lỗi và hướng giải quyết, không có nội dung bán hàng
- Không có profiling consent → nội dung chung, ghi rõ "không cá nhân hóa"

C8. Human in the loop
- Nút: Approve / đổi channel / đổi tone / đổi offer / Reject (kèm lý do)
- Log: inputs, rule đã áp dụng, scores, quyết định cuối, người duyệt, thời gian
- Chế độ service agent: nếu khách đang có ticket mở, card phải chuyển sang
  "xử lý trước" (P-SV-01) với gợi ý câu nói cho agent

═══════════════════════════════════════════
# ONTOLOGY / KNOWLEDGE GRAPH
═══════════════════════════════════════════
Node: Customer, Contract(Energy|Mobile|Autostrom), Device, Order, Ticket, Session,
Signal, Need, Offer (product_catalog), Channel, Consent, Exclusion, Action(history)
Edge: HOLDS, OWNS_DEVICE, PLACED, RAISED, EMITTED, INDICATES, ADDRESSED_BY,
DELIVERED_VIA, REQUIRES, BLOCKS, RECEIVED, RESPONDED
Vai trò của KG: sinh offer ứng viên từ signal, áp dụng luật (BLOCKS/REQUIRES),
tạo đường giải thích. Xếp hạng luôn theo ΔCLV.

# Luật bắt buộc
Giữ nguyên danh sách hard rules từ đề bài, cộng thêm:
- Áp dụng luật TRƯỚC khi xếp hạng
- Bỏ ΔCLV ≤ 0
- Dữ liệu thanh toán chỉ dùng làm exclusion
- Thiếu dữ liệu thì hiển thị "không đủ dữ liệu", không suy đoán

# Kiểm thử bằng khách hàng thật trong mock data
- MG-100051 / MG-100060: gas meter deregistered → kỳ vọng StromWärme
- MG-100096: gas meter deregistered NHƯNG dunning ≥ 2 → kỳ vọng P-SV-01, sales bị chặn
- MG-100186: gas meter deregistered NHƯNG có complaint đang mở → kỳ vọng service trước
- MG-100068: gas meter deregistered + Wallbox nhưng chưa có Autostrom → hai signal
  cạnh tranh; kiểm tra xếp hạng
- MG-100023 / MG-100112: mua Wallbox, chưa có Autostrom → P-AS-01
- MG-100009 / MG-100659: ≥ 3 lần sạc failed trong 09/2026 → P-SV-01
- MG-100035 / MG-100087: cancellation_pending → không có sales offer
- MG-100004 / MG-100012: không có profiling consent → fallback không cá nhân hóa
  (MG-100004 có thêm complaint đang mở)

# Output
[Stack: React / Streamlit ...]
Với mỗi khách: 1 JSON {profile, signals[], timeline[], candidates[], blocked[], chosen,
explanation_path[], decision_log} và UI render từ JSON này.
```
