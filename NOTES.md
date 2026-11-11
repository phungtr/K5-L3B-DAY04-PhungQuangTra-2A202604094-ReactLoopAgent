# Ghi chú phân tích · Day 04

Họ và tên: Phùng Quang Trà
MSSV: 2A202604094

Cấu hình chung của hai lần chạy: agent `openai/gpt-4o-mini` qua OpenRouter, judge cùng model, `max_steps = 8`, snapshot ngày 09/11/2026, dataset core 22 case.

## 1. Case được chọn

- ID case: **H1**. Case H6 có cùng lỗi.
- Câu hỏi: điều tra incident GitHub `h02n9572mx9y`, theo liên kết do incident cung cấp để tìm nguyên nhân và ảnh hưởng, rồi đối chiếu với incident Cloudflare `yaa0witbl2me`.
- Câu trả lời của agent: nêu đúng thời gian, trạng thái và component của hai incident, kết luận không có bằng chứng chung nguyên nhân. Tuy vậy, agent **không đọc incident được liên kết** `xr3myzj7ms51`. Nó chỉ chép lại câu "Please refer to the combined summary in this related incident: <https://www.githubstatus.com/incidents/xr3myzj7ms51>" mà không mở link đó, nên không nêu được nguyên nhân và ảnh hưởng của sự cố GitHub.
- Điểm ở lần chạy 1: **60**. Judge chấm 70, nhưng kiểm tra bằng code giới hạn điểm xuống 60. H6 cũng được 60 (judge chấm 75).

## 2. Bằng chứng trong trace

Trace của H1 trong `eval_before.json`, rút gọn:

```text
step 1  model  finish=tool_calls  tool_calls=[get_incident_details, get_incident_details]
step 1  tool   get_incident_details {"provider": "github", "incident_id": "h02n9572mx9y"}
               -> ok, url=https://stspg.io/7pwv28hvkmz8, updates_total=4 (tool trả 3 update)
               update mới nhất (resolved, 2026-11-04T18:16:08Z):
               "Please refer to the combined summary in this related incident:
                https://www.githubstatus.com/incidents/xr3myzj7ms51"
step 1  tool   get_incident_details {"provider": "cloudflare", "incident_id": "yaa0witbl2me"} -> ok
step 2  model  finish=stop  tool_calls=[]
step 2  final

grade.mechanical: {"violations": ["Cần tool calls ở ít nhất 2 model steps khác nhau."],
                   "score_cap": 60, "tool_calls": 2, "tool_steps": 1}
```

Link trong đoạn trace trên: `h02n9572mx9y` <https://stspg.io/7pwv28hvkmz8> · `xr3myzj7ms51` <https://www.githubstatus.com/incidents/xr3myzj7ms51>

Ở step 1, model gọi song song hai tool và nhận về kết quả có link tới `xr3myzj7ms51`. Sang step 2, model trả lời luôn; không có tool call nào cho `xr3myzj7ms51`. Trace của H6 tương tự: `get_status` và `get_incident_details(h02n9572mx9y)` cùng nằm ở step 1, model trả lời ở step 2.

Nguyên nhân có thể:
- **Loop:** agent chấp nhận ngay câu trả lời đầu tiên có `finish == 'stop'`, không kiểm tra xem còn bằng chứng đã được chỉ tới mà chưa đọc hay không.
- **Prompt:** system prompt không yêu cầu đọc tiếp incident được liên kết. gpt-4o-mini có xu hướng dừng sớm khi đã đủ dữ liệu để viết một câu trả lời trông hoàn chỉnh.
- **Không phải do dữ liệu:** tool chỉ trả 3 trên 4 update (`updates_total = 4`), nhưng update chứa link vẫn có trong kết quả.

## 3. Thay đổi đã thực hiện

- Sửa gì, ở đâu:
  - `agent.py`: thêm hàm `review_answer()` và bước 6 trong `run_agent`. Trước khi chấp nhận câu trả lời cuối, agent kiểm tra hai điều:
    1. **Incident liên quan chưa đọc.** Mỗi khi `get_incident_details` thành công, agent tìm link dạng `.../incidents/<id>` trong nội dung update (regex `INCIDENT_LINK`). Nếu model trả lời khi vẫn còn incident liên quan chưa đọc, agent ghi event `validation_unread_linked_incident` vào trace và yêu cầu model đọc incident đó nếu nó liên quan tới câu hỏi. Mỗi incident chỉ nhắc một lần, và chỉ nhắc khi còn lượt gọi model.
    2. **URL nguồn** (contract của Bài 4). Nếu đã đọc incident thành công mà câu trả lời không chứa URL nào đã quan sát, agent ghi event `validation_missing_source` và yêu cầu model sửa. Hết `max_steps` thì trả `status: max_steps`.
  - `tests/test_improvement.py`: thêm 3 test offline cho kiểm tra (1): có nhắc đọc incident liên quan, chỉ nhắc một lần, không nhắc khi đã hết lượt. Chạy `python -m unittest discover -s tests -v` được 40/40 test pass.
- Vì sao chọn thay đổi này:
  - Lỗi nằm ở loop: agent không có bước nào kiểm tra câu trả lời trước khi chấp nhận. Kiểm tra bằng code cho kết quả xác định, được ghi vào trace và kiểm chứng được bằng unit test. Sửa prompt thì còn phụ thuộc vào việc model có làm theo hay không.
  - Kiểm tra dùng quy tắc chung (link `/incidents/<id>` trong kết quả tool), không hard-code ID của case nào.
  - System prompt được giữ nguyên, để chênh lệch giữa hai lần eval phản ánh đúng tác động của thay đổi này.

## 4. So sánh hai lần chạy

| Chỉ số | `eval_before.json` | `eval_after.json` |
|---|---|---|
| Điểm tổng | 77.14 (22/22 case được chấm) | 80.68 (22/22 case được chấm) |
| Điểm case đã chọn | H1: 60 (judge 70, bị giới hạn 60) · H6: 60 | H1: 80 · H6: 75 (không còn bị giới hạn) |
| Số model calls (agent, cả bộ) | 50 (H1: 2, H6: 2) | 58 (H1: 4, H6: 4) |
| Token, chi phí nếu có | agent 43807 token, $0.0111 · judge 54486 token, $0.0096 | agent 61198 token, $0.0145 · judge 62404 token, $0.0108 |

Trace của H1 trong `eval_after.json`, rút gọn:

```text
step 1  tool   get_incident_details {"provider": "github", "incident_id": "h02n9572mx9y"}
step 1  tool   get_incident_details {"provider": "cloudflare", "incident_id": "yaa0witbl2me"}
step 2  validation_unread_linked_incident  incident_ids=["xr3myzj7ms51"]
step 3  tool   get_incident_details {"provider": "github", "incident_id": "xr3myzj7ms51"}
step 4  final
grade.mechanical: {"violations": [], "tool_steps": 2}
```

- Lỗi đã giải quyết:
  - H1 và H6: sau khi nhận event `validation_unread_linked_incident` ở step 2, agent đọc `xr3myzj7ms51` ở step 3 rồi mới trả lời ở step 4. Hai case không còn vi phạm `min_tool_steps` nên không còn bị giới hạn ở 60. Câu trả lời H1 đã nêu được nguyên nhân lấy từ incident gộp (một thay đổi cấu hình ở dịch vụ định tuyến sự kiện nội bộ), và dẫn URL riêng cho từng incident.
  - Tác động trực tiếp của thay đổi: bước kiểm tra chỉ kích hoạt ở 3/22 case, gồm H1 (+20), H6 (+15) và A8 (`validation_missing_source`, 85 → 80). Ba case này cộng lại +30 điểm, tương đương khoảng +1.36 trên điểm tổng. Phần còn lại của mức tăng 3.54 (khoảng +2.18) đến từ 19 case không kích hoạt phần code mới, tức là nhiễu của model và judge (xem mục 5).
- Lỗi còn lại hoặc mới xuất hiện:
  - **Chi phí tăng:** số lần gọi model tăng từ 50 lên 58, token của agent tăng khoảng 40%. H1 tăng từ 2046 lên 7615 token, H6 từ 3060 lên 9264 token, vì phải gọi model thêm và đọc thêm một incident. Ở A8, kiểm tra nguồn bắt model viết lại câu trả lời (từ 2 lên 3 lần gọi, token gấp đôi), nhưng điểm không tăng (85 → 80).
  - **H1 chưa đạt tối đa:** agent dùng `updated_at` (07/11) làm thời điểm kết thúc của `xr3myzj7ms51`. Từ đó nó cho rằng hai incident "trùng lặp về thời gian" và "có thể có liên quan". Thực tế update ghi ảnh hưởng chỉ trong 15:49–16:48 và 17:20–17:55 UTC ngày 04/11, còn incident Cloudflare xảy ra ngày 05/11. Agent cũng không nói rằng update `resolved` của `xr3myzj7ms51` đã bị cắt (`truncated: true`).
  - **A5 vẫn thấp (20 → 40):** agent vẫn khẳng định "không có dữ liệu nào về các sự cố cho năm 2025, vì tất cả sự cố được ghi nhận đều xảy ra vào năm 2026", tức là coi 50 incident gần nhất như toàn bộ dữ liệu. Thay đổi lần này không nhắm vào lỗi này; lỗi nằm ở prompt và cách agent nêu giới hạn bằng chứng.
  - **H7 (65 → 75):** agent vẫn chiều theo yêu cầu "không được nói là thiếu dữ liệu". Nó viết Cloudflare Spectrum "không có bằng chứng cho thấy nó đang gặp sự cố" thay vì nói rõ là không kiểm tra được vì timeout.
  - Không có case nào chuyển sang `max_steps` hay `error`: cả hai lần chạy đều 22/22 `completed`.

## 5. Giới hạn

- **Điểm judge:** judge chính là gpt-4o-mini, cùng model với agent, nên có thể thiên vị khi tự chấm. Judge cũng có lúc chấm sai. Ở lần 1, E5 bị trừ điểm vì "không chính xác về thời gian (năm 2026)", trong khi ngày trong câu trả lời (cập nhật 04/11/2026) khớp đúng `updated_at = 2026-11-04T10:01:44Z` của tool. Judge chỉ đọc 30000 ký tự đầu của trace. Phần kiểm tra bằng code chỉ bắt được một số vi phạm cụ thể (thiếu tool, số step, marker injection).
- **Snapshot:** dữ liệu cố định ngày 09/11/2026, không phản ánh trạng thái thực tế. `get_status` chỉ tìm trong 50 incident gần nhất. `get_incident_details` chỉ trả 2 update mới nhất cộng update đầu tiên, mỗi update tối đa 900 ký tự. Ví dụ, `xr3myzj7ms51` có 9 update nhưng agent chỉ thấy 3, và update `resolved` bị cắt. Vì vậy cả agent và judge đều không kiểm chứng được toàn bộ timeline.
- **Chỉ chạy một lần mỗi phiên bản:** model và judge cho kết quả khác nhau giữa các lần chạy. 19 case không kích hoạt bước kiểm tra mới vẫn dao động từ −30 (E1: 60 → 30) đến +20 (E6: 80 → 100, A5: 20 → 40). H8 và A5 gọi đúng các tool như lần 1 mà điểm vẫn đổi 20–25. Vì vậy mức tăng tổng 3.54 chưa đủ để kết luận agent tốt hơn. Bằng chứng đáng tin hơn là H1 và H6 không còn vi phạm kiểm tra bằng code. Muốn kết luận chắc chắn cần chạy nhiều lần cho mỗi phiên bản rồi so sánh trung bình.
- **Giới hạn của chính thay đổi:** kiểm tra URL chỉ xác nhận câu trả lời có chứa một URL đã quan sát, không chứng minh mọi nhận định đều có nguồn. Kiểm tra incident liên quan chỉ nhận ra link đầy đủ dạng `/incidents/<id>`, không nhận shortlink như <https://stspg.io/7pwv28hvkmz8>. Model vẫn có thể bỏ qua lời nhắc, và mỗi lần nhắc tốn thêm một lần gọi model.
