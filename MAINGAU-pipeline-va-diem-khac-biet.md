# MAINGAU NBA: pipeline, điểm khác biệt, vai trò của Ontology và KG

26/10/2026 · Tài liệu thống nhất cho cả đội · Pitch bằng tiếng Anh, nội dung gửi khách bằng tiếng Đức

Các số liệu trong file được đếm từ mock data (`data/maingau_nba_mockdata.xlsx` và `data/event_stream_2026-10-01.jsonl`) ngày 26/10. Tài liệu `MAINGAU-tai-lieu-tong-the-va-ke-hoach-trien-khai.md` được soạn **trước khi có đề**; khi hai file khác nhau, theo file này.

---

## 1. Làm gì, trong một đoạn

Mình xây **một engine Next Best Action**. Với mỗi khách, engine đề xuất:

- **offer** (hoặc action service, hoặc "không liên hệ"),
- **kênh**,
- **tone Du/Sie**,
- **ΔCLV kỳ vọng**,
- **một dòng lý do**.

Marketing duyệt trước khi gửi. Engine luôn đúng consent và exclusion, **kể cả khi dữ liệu thay đổi theo thời gian thực**.

| Đề bài yêu cầu | Ghi chú |
|---|---|
| Prototype click được | Offer, kênh, tone, ΔCLV, lý do cho từng khách |
| Dashboard marketing | Điều khiển, duyệt, theo dõi NBA |
| Customer 360° | Cho agent service: trạng thái, CLV, top NBA kèm lý do |
| 1 slide kiến trúc | Databricks + MCP |
| Pitch | 8 phút + 4 phút Q&A |
| Deep dive (chọn 1) | **Đội chọn B: Data freshness & event replay.** Phần A (uplift) chỉ trình bày khái niệm |
| Cách chấm | Kỹ thuật 25 · Khả thi 25 · Tác động 25 · Sáng tạo 15 · Pitch 10. Kiểm trên **khách tham chiếu ẩn**: ΔCLV, **0 vi phạm consent/exclusion**, có lý do cho mọi quyết định |

---

## 2. Pipeline toàn cảnh

Bản Mermaid nằm trong [`diagrams/`](diagrams/): pipeline, vòng event, ontology KG và hai ví dụ khách. Import được vào mermaid.live, draw.io, Notion, GitHub. Bản xem trực tiếp có nút copy: [NBA Engine Pipeline](https://claude.ai/artifact/K7qthtmvC5yDFiFbHHbT55). Link này đang ở chế độ riêng tư; muốn cả đội mở được thì vào menu Share để chia sẻ.

```text
                        NGUỒN DỮ LIỆU
   ┌───────────────────────────────┐   ┌─────────────────────────────────────┐
   │ Snapshot 30.09 (16 bảng,      │   │ Event stream 01.10                  │
   │ 750 khách, một customer_id)   │   │ 647 dòng → 635 event sau khi bỏ trùng│
   └───────────────┬───────────────┘   └──────────────────┬──────────────────┘
                   ▼                                      ▼
 ① NẠP VÀ LÀM SẠCH
   bỏ trùng theo event_id · hai đồng hồ (occurred_at / ingested_at) · bỏ lượt mở do máy (Apple MPP)
   bỏ đơn khách vãng lai · CDR roaming về trễ · ticket ID lạ → ghép theo khách
                   ▼
 ② TRẠNG THÁI KHÁCH "AS-OF"  ◄─────────────────────────────────────────┐
   sản phẩm đang có · consent mới nhất · case đang mở · dunning · tín hiệu   │
   CLV hiện tại · độ mới của từng nguồn                                    │
                   │                    ┌──────────────────────────────┐   │
                   │◄───────────────────┤ KG CHÍNH SÁCH VÀ SẢN PHẨM      │   │
                   │                    │ ontology, khoảng 60–80 node,  │   │
                   ▼                    │ có phiên bản                   │   │
 ③ TÍN HIỆU → NHU CẦU → ỨNG VIÊN         └──────────────────────────────┘   │
   duyệt KG: event/tín hiệu → nhu cầu → action                            │
                   ▼                                                      │
 ④ CỔNG CỨNG, chặn kèm mã lý do                                           │
   consent theo kênh → consent profiling → exclusion → sản phẩm đã có → độ mới dữ liệu
                   ▼                                                      │
 ⑤ CHẤM ĐIỂM ΔCLV đúng clv_method                                         │
   p_accept·(CLV_accept − CLV_now) + (1 − p_accept)·(CLV_reject − CLV_now) − chi phí liên hệ
                   ▼                                                      │
 ⑥ PHÂN XỬ                                                                │
   xếp hạng · bỏ ΔCLV âm · giới hạn liên hệ · 10% control group           │
                   ▼                                                      │
 ⑦ KÊNH VÀ TONE   ⑧ NỘI DUNG (template đã duyệt, tiếng Đức)               │
                   ▼                                                      │
 ⑨ LÝ DO MỘT DÒNG + LOG đầy đủ (input, luật, điểm, action đã chọn)          │
                   ▼                                                      │
 ⑩ HUMAN-IN-THE-LOOP                                                      │
   Marketing duyệt từng lô · Agent dùng trong Customer 360                 │
                   ▼                                                      │
 ⑪ XUẤT / HÀNG ĐỢI GỬI (engine không tự gửi)                               │
                   ▼                                                      │
 ⑫ PHẢN HỒI VÀ HỌC: response, control group, uplift (khái niệm) ───────────┘
```

### Vòng xử lý event (phần deep dive B)

```text
event mới ─► bỏ trùng ─► cập nhật trạng thái khách đó (theo occurred_at, biết lúc ingested_at)
          ─► KG cho biết event này chạm dữ kiện nào, cổng và luật nào phụ thuộc vào nó
          ─► tính lại ③–⑨ CHỈ cho khách bị ảnh hưởng
          ─► action đang chờ không còn hợp lệ → THU HỒI, kèm lý do "revoked by event X"
          ─► đề xuất mới → hàng duyệt của marketing
```

**Ví dụ thật trong stream:**

| Khách | Event | Engine phải làm |
|---|---|---|
| MG-100003 | Rút consent profiling và newsletter lúc 10:14:00; nạp lúc 10:14:05 | Thu hồi trong vài giây |
| MG-100465 | Hủy hợp đồng lúc 09:17 ngày 01.10; **hôm sau 02:11 mới nạp** | Thu hồi offer bán hàng đã đề xuất trong ngày 01.10 |
| MG-100004 | Dunning 2→3, nạp trễ 25 giờ | Không đổi vì khách đã bị chặn bán; log ghi nhận |

### Từng bước: input, output, phụ trách

| Bước | Dữ liệu chính | Output | Phụ trách |
|---|---|---|---|
| ① Nạp | Toàn bộ sheet + JSONL; `sources` cho độ trễ | Bảng sạch, event đã bỏ trùng | Backend |
| ② Trạng thái | Hợp đồng, consent, ticket, `customer_value` | Trạng thái khách tại thời điểm t | Backend |
| ③ Ứng viên | KG + tín hiệu (gỡ đồng hồ gas, hết bảo đảm giá, wallbox, sạc lỗi, chạm data…) | Danh sách action có căn cứ | Domain / KG |
| ④ Cổng cứng | `consent_status`, dunning, hủy hợp đồng, ticket mở, sản phẩm đã có | Hợp lệ / bị loại (mã lý do) | Domain / KG + Engine |
| ⑤ Chấm điểm | `clv_method`, `value_assumptions`, `product_catalog`, `nba_action_history` | ΔCLV từng action | Engine |
| ⑥ Phân xử | Lịch sử liên hệ, tham số giới hạn | Action được chọn + phương án thay thế | Engine |
| ⑦ Kênh, tone | Consent theo kênh, phiên portal, app, lượt mở thật, câu chữ ticket/transcript | Kênh + Du/Sie | AI / Engine |
| ⑧ Nội dung | Template đã duyệt | Câu tiếng Đức điền slot | AI |
| ⑨ Lý do + log | Đường đi trong KG + thành phần ΔCLV | Một dòng lý do, bản ghi quyết định | Engine |
| ⑩–⑪ HITL, xuất | Kết quả ③–⑨ | Duyệt, override có mã lý do, thu hồi | Frontend + Backend |
| ⑫ Học | Phản hồi, control group | p_accept cập nhật; thiết kế holdout | Engine / đánh giá |

---

## 3. Ba giao diện phục vụ pipeline

| Giao diện | Người dùng | Hiển thị | Thao tác |
|---|---|---|---|
| **Prototype engine** | Jury, đội | Từng khách: action, kênh, tone, ΔCLV, lý do, các phương án bị loại | Chọn khách, replay event |
| **Dashboard marketing** | Caro / marketing | Lô theo nhóm (action × kênh × tone), tổng ΔCLV, khách mẫu, danh sách thu hồi, độ mới nguồn | Duyệt lô, chỉnh lever và giới hạn, xem trước tác động, override có lý do |
| **Customer 360°** | Agent service | Sản phẩm, hợp đồng, case đang mở, CLV, top NBA kèm lý do, nhãn độ mới | Dùng hoặc bỏ gợi ý (có lý do), kích hoạt xử lý service |

Thêm **một slide kiến trúc** (mục 8).

---

## 4. Điểm khác biệt

### 4.1 Những thứ không khác biệt (đội nào cũng có)

- **Công thức xếp hạng.** MAINGAU đưa sẵn; cách xếp NBA kiểu này là chuẩn ngành (Pega xếp theo P×C×V×L).
- **Dùng LLM viết tin nhắn.**
- **Có dashboard.**

Không pitch những thứ này như điểm mới.

### 4.2 Năm điểm khác biệt của mình

| # | Khác biệt | Bằng chứng từ data | Khoảnh khắc demo |
|---|---|---|---|
| **D1** | **Vẫn đúng khi dữ liệu thay đổi.** Event làm thu hồi ngay action không còn hợp lệ; hai đồng hồ; bỏ trùng; dữ liệu về trễ | Engine cũ: khoảng **334 lần gửi** qua kênh khách đã rút consent *trước* đó (theo cách ghép kênh–consent, cần xác nhận), **70** action newsletter sau khi khách đã unsubscribe | Replay MG-100003: rút consent lúc 10:14, action biến mất kèm lý do. Kiểm tra "0 vi phạm sau khi replay toàn bộ stream" |
| **D2** | **Service trước bán hàng, bằng chính con số giá trị.** Chào bán khi khách có case mở cho ΔCLV âm, nên engine tự chọn xử lý service | Pilot hỗ trợ agent của MAINGAU: 55/100 gợi ý bị bỏ qua, 30 lần vì `customer_upset` | MG-100009: lần sạc lỗi thứ 4, agent gợi ý StromAktiv bị bỏ; engine của mình chọn chủ động xử lý service |
| **D3** | **Lý do đọc được:** đường đi trong KG + thành phần ΔCLV + phương án bị loại kèm lý do | Đề yêu cầu "one line why… and change it" | Bấm vào một khách → đọc một dòng → marketing đổi lever → thấy quyết định đổi |
| **D4** | **Xử lý bẫy dữ liệu và đo được** so với engine cũ | 1.589 lượt mở do máy so với 1.457 lượt người mở; Autostrom chào 72/203 lần cho khách đã có; 81 action bán hàng tới khách đang nợ | Bảng "legacy so với engine mới" ở dashboard |
| **D5** | **Trung thực về phần Learn.** Nói rõ cái gì chưa chứng minh được, và thiết kế để chứng minh | Control: 248 dòng, chỉ **5 lượt chuyển đổi**, nên không đo được uplift từng offer | Một slide: thiết kế holdout cho production, p_accept được co rút theo cấp |

**Câu chốt:** *"Every recommendation stays correct when the data changes, and every one comes with a reason you can read and change."*

---

## 5. Ontology và KG giúp gì

### 5.1 KG ở đây là gì

- Một **đồ thị chính sách và sản phẩm** nhỏ, khoảng 60–80 node, có phiên bản. Lưu bằng JSON/YAML, nạp vào NetworkX.
- Dữ liệu khách **vẫn nằm ở bảng**, nối vào đồ thị qua `customer_id` lúc chạy.
- Không dùng graph database; không để LLM "suy luận" trên đồ thị.

```text
Signal/Event ──indicates(ngưỡng)──► Need ──servedBy──► Action ──valueKey──► value_assumptions
  gas_meter_deregistration            HEAT_PUMP           P-EN-03 StromWärme
  charge_failed ×3/30d                SERVICE_ISSUE       P-SV-01 Service fix
  mobile_data_threshold               MORE_DATA           P-MO-02 Upgrade
  price_guarantee_end <90d            RETENTION_RISK      P-EN-02 StromGarant
  cart_abandoned(Wallbox)             HOME_CHARGING       P-SH-02 Wallbox

Action ── type ──► SALES | UPSELL | RETENTION | ONE_OFF | SERVICE
Action ── requiresNotHeld / requires ──► Product           (không chào sản phẩm đã có)
Action ── blockedBy ──► Exclusion {dunning, open_complaint, cancellation}   (chặn SALES, không chặn SERVICE)
Action ── deliveredVia ──► Channel ── requiresConsent ──► ConsentType
Template ── for ──► (Action × Channel × Tone), approved = true
Attribute ── purpose ──► SCORING | EXCLUSION_ONLY (dữ liệu thanh toán) | PROFILING_REQUIRED (dữ liệu hành vi)
EventType ── updates ──► Fact ── usedBy ──► Gate / Rule    (để biết event nào phải tính lại cái gì)
```

### 5.2 Sáu vấn đề KG giải quyết

| # | Vấn đề | KG giải thế nào | Ví dụ |
|---|---|---|---|
| K1 | "Offer nào *có lý* với khách này?" | Duyệt từ tín hiệu, qua nhu cầu, tới action; mỗi edge có ngưỡng bằng chứng | MG-100125 gỡ đồng hồ gas → HEAT_PUMP → StromWärme |
| K2 | **Luật cứng nằm rải rác, dễ sót** | Một nơi khai báo: kênh nào cần consent nào; exclusion chặn loại action nào; sản phẩm đã có thì loại | Không chào Autostrom cho MG-100007 vì khách đã có |
| K3 | **Lý do một dòng** | Lý do được sinh từ đường đi + điểm số, không phải đoạn LLM tự viết | "ChargingFailed ×4 → ServiceIssue → Service fix · ΔCLV +€X · Sales blocked: open service case" |
| K4 | **Event mới thì tính lại gì, cho ai?** | `EventType → Fact → Gate/Rule` cho biết chính xác phần nào phải tính lại và action nào phải thu hồi | consent_changed → cổng consent → thu hồi action newsletter của MG-100003 |
| K5 | **Marketing tự điều chỉnh** | Lever, edge và template là dữ liệu có phiên bản: duyệt, phát hành, audit | Tắt Mobil cho phân khúc X, xem trước tác động |
| K6 | **Mục đích dùng dữ liệu** | Gắn nhãn thuộc tính: dữ liệu thanh toán chỉ dùng để loại trừ; dữ liệu hành vi cần consent profiling | MG-100004 không có consent profiling, nên tone giữ mặc định |

### 5.3 Không giao cho KG

- **Tính CLV:** dùng `clv_method`. Công thức tái tạo `clv_eur` với sai số trung vị 0,27 €.
- **Xếp hạng:** code tất định.
- **Lưu toàn bộ 750 khách × 16 bảng.**
- **Quyết định consent bằng suy luận mềm.**

Nếu thiếu edge hay thiếu dữ kiện thì **chặn kèm lý do**, không bao giờ hiểu là "được phép".

---

## 6. Ba ví dụ đi qua toàn bộ pipeline

**MG-100009: service trước bán hàng**

```text
① 17:22 event charge_session_failed (Hanau) → lần lỗi thứ 4 trong 30 ngày
② trạng thái: Autostrom active · churn 0,34 (driver "3 failed charges") · không có consent marketing nào
③ KG: charge_failed ×4 → SERVICE_ISSUE → P-SV-01 · StromAktiv cũng là ứng viên
④ StromAktiv: không có kênh marketing hợp lệ, và đang có service case → loại (có lý do)
⑤ P-SV-01: bỏ các yếu tố churn do service, trừ 15 € chi phí xử lý → ΔCLV dương
⑨ "4 failed charges in 30d → proactive fix · ΔCLV +€X · no sales: open service issue"
⑩ hiện cho agent trong Customer 360 (khách đang gọi)
```

Câu hỏi mở cho mentor: liên hệ service có cần consent marketing không?

**MG-100003: rút consent giữa ngày**

```text
trước 10:14: có thể có đề xuất qua newsletter
10:14:05 nạp consent_changed (profiling, newsletter → withdrawn)
→ KG: consent_changed ảnh hưởng cổng consent và cổng profiling
→ tính lại riêng MG-100003 → thu hồi action newsletter, không còn cá nhân hóa
→ log "revoked by event e-…" · dashboard hiện trong danh sách thu hồi
```

**MG-100005: trigger theo thời gian thực**

```text
18:30 mobile_data_threshold 80 %, còn 11 ngày · 3/3 tháng đã chạm giới hạn · hộ 4 người, 1 SIM
→ ứng viên Mobil Upgrade và Zusatz-SIM → tính ΔCLV
→ kênh: app push hoặc SMS (có consent; marketing email chưa có)
→ tone Du: khách viết "Hi… 😅" và có consent profiling
```

---

## 7. Dữ liệu: số cần nhớ và bẫy phải xử lý

| Chủ đề | Số liệu |
|---|---|
| Khách | 750 (khoảng 150 chỉ có Autostrom); 67 bị chặn bán tại snapshot (dunning ≥ 1: 31; khiếu nại mở: 29; đang hủy: 8) |
| Tín hiệu | Bảo đảm giá hết < 90 ngày: 144 · gỡ đồng hồ gas: 12 (+1 trong stream) · có điện chưa có Mobil: 452 · chạm data ≥ 2/3 tháng: 11 |
| Consent | Profiling: 461 đồng ý / 289 không; phone chỉ 125, SMS 75 đồng ý |
| Lịch sử action | 2.270 action; control 248 (11%); chuyển đổi: được gửi 3,4%, control 2,0% |
| p_accept | Co rút theo cấp: offer → kênh → tone. Chỉ học từ lần gửi tới khách **chưa có** sản phẩm. 8 sản phẩm chưa có lịch sử (StromWärme, Zusatz-SIM…) dùng prior có nhãn |
| Tone | Câu chữ ticket gồm 25 mẫu, rõ Du/Sie (320 Sie, 238 Du); chỉ cá nhân hóa khi có consent profiling |
| Event stream | 12 dòng trùng; 100 event lệch thứ tự theo `occurred_at`; nạp trễ tới 47 giờ; `newsletter_opened` thiếu phân loại người/máy; 6 khiếu nại mới; 2 thông báo hủy về trễ |
| Khách kịch bản | **MG-100001 → 010**, mỗi khách thử một luật. Dùng làm bộ acceptance test, kỳ vọng ghi rõ là của đội |

---

## 8. Slide kiến trúc (mục tiêu, không phải đã triển khai)

```text
Nguồn (CRM, ERP, Telco, Shopware, HEMS, Autostrom, ESP, Ticketing)
  → nạp batch và streaming vào Delta tables (Unity Catalog)
  → bảng trạng thái khách as-of + bảng KG chính sách (node/edge)
  → Decision service: cổng kiểm, chấm ΔCLV, phân xử; log quyết định
  → dashboard marketing và Customer 360; hàng đợi gửi sau khi duyệt
  → hàm kiểm luật và tra cứu khách đưa ra dạng Unity Catalog functions
     (managed MCP server, hiện vẫn Public Preview) để agent và trợ lý gọi được
```

---

## 9. Đã chốt và còn mở

| Đã chốt | Còn mở, hỏi mentor (Raphael, Caro, Jan) |
|---|---|
| Deep dive **B**; A chỉ ở mức khái niệm | Kênh nào ứng với loại consent nào (portal pop-up, app push dùng `portal_app_personalisation`?) |
| Xếp hạng đúng `clv_method`; không tự đổi công thức | Liên hệ **service** có cần consent marketing không? (MG-100009) |
| Thứ tự cổng: consent kênh → profiling → exclusion → sản phẩm đã có → độ mới | Khách đang hủy hợp đồng: offer giữ chân có bị coi là "sales content"? |
| Tone chỉ cá nhân hóa khi có consent profiling; mặc định "Sie" | Thêm business line có cộng 12 €/năm chi phí phục vụ không? |
| Engine không tự gửi; marketing duyệt từng lô; luật cứng không override được | Giới hạn liên hệ (số lần / số ngày) là bao nhiêu? 7 khách chọn English thì gửi nội dung bằng gì? |
| 10% control cố định cho engine mới | |

---

## 10. Phân việc theo pipeline

| Vai trò | Phần pipeline | Bàn giao đầu tiên |
|---|---|---|
| Backend / dữ liệu | ① ② ⑪ + replay | Trạng thái as-of + replay bỏ trùng, hai đồng hồ |
| Domain / KG | ③ ④ + chính sách | KG JSON + danh sách cổng có mã lý do |
| Engine / đánh giá | ⑤ ⑥ ⑨ ⑫ + test | ΔCLV đúng `clv_method`; 10 test khách kịch bản; test "0 vi phạm sau replay" |
| AI | ⑦ ⑧ | Phát hiện Du/Sie bằng luật; template tiếng Đức đã duyệt |
| Frontend / demo | ③ giao diện + ⑩ | Prototype, dashboard marketing, Customer 360 |

**Thứ tự build:** đi theo đúng thứ tự pipeline. Có **một khách đi trọn ①→⑪** trước, rồi mới mở rộng sang 750 khách và replay stream.
