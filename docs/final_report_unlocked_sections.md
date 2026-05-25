<!--
Nội dung này dành cho các phần không bị khóa của template báo cáo.
Trang bìa, cam kết tác giả, lời cảm ơn và tài liệu tham khảo giữ nguyên theo file mẫu.
-->

# Tóm tắt Bài tập lớn

Bài tập lớn xây dựng một hệ thống Data Warehouse cho dữ liệu thương mại điện tử, tập trung vào quy trình đưa dữ liệu đơn hàng từ nguồn vận hành sang kho dữ liệu phục vụ phân tích. Hệ thống sử dụng MongoDB làm nơi tiếp nhận dữ liệu nguồn ở dạng document, sau đó dùng pipeline ETL bằng Python để chuyển dữ liệu qua các lớp Bronze, Silver và Gold trong PostgreSQL. Cách tổ chức phân tầng này giúp dữ liệu được lưu lại ở trạng thái thô, được làm sạch có kiểm soát, rồi được nạp vào mô hình phân tích ổn định.

Ở lớp Gold, nhóm thiết kế mô hình Star Schema với bảng sự kiện trung tâm `dw.fact_sales` và các bảng chiều như khách hàng, sản phẩm, nhà bán lẻ, địa chỉ, thanh toán và thời gian. Mô hình này phù hợp với các truy vấn OLAP như phân tích doanh thu theo ngày, sản phẩm, khách hàng, khu vực hoặc phương thức thanh toán. Ngoài phần mô hình dữ liệu, hệ thống còn ghi nhận audit theo từng batch trong `etl.batch_run`, lưu kết quả kiểm tra chất lượng dữ liệu trong `dq.check_results`, và giữ thông tin lineage từ Gold ngược về Silver/Bronze thông qua `silver_id`, `bronze_id`, `batch_id`.

Dữ liệu thực hành được lấy từ bộ dữ liệu Olist e-commerce local trong thư mục `data/olist/raw`. Pipeline hiện tại chỉ sử dụng nguồn Olist cho các lần chạy thông thường. Bộ CSV hiện có gồm 99.441 đơn hàng, 112.650 dòng order item; với bộ lọc trạng thái `delivered`, pipeline tạo được 110.197 document ở mức order-item và 96.478 đơn hàng giao thành công duy nhất. Hệ thống được đóng gói bằng Docker Compose, có service import Olist vào MongoDB, service ETL, PostgreSQL, MongoDB và dashboard web cục bộ để quan sát Gold sales, trạng thái batch và kết quả Data Quality.

Kết quả của bài tập lớn là một prototype Data Warehouse có thể chạy lại được, thể hiện được các khái niệm cốt lõi của môn Hệ quản trị cơ sở dữ liệu: thiết kế kho dữ liệu, mô hình đa chiều, ETL, kiểm soát chất lượng dữ liệu, audit, metadata vận hành và truy vấn phân tích. Hệ thống chưa hướng tới mức production hoàn chỉnh, nhưng đủ để minh họa một quy trình dữ liệu end-to-end từ nguồn thô đến lớp phân tích.

# Mục lục đề xuất

- Phần I - Lý thuyết
  - 1.1. Tổng quan về Data Warehouse
  - 1.2. Thiết kế Data Warehouse và mô hình đa chiều
  - 1.3. Quy trình ETL/ELT
  - 1.4. Nền tảng triển khai Data Warehouse
  - 1.5. OLAP và truy vấn phân tích
  - 1.6. Ứng dụng Data Warehouse trong BI và thương mại điện tử
- Phần II - Thực hành
  - 2.1. Bài toán và phạm vi triển khai
  - 2.2. Kiến trúc hệ thống
  - 2.3. Dữ liệu nguồn Olist và mô hình dữ liệu
  - 2.4. Thiết kế Bronze/Silver/Gold và Star Schema
  - 2.5. Quy trình ETL trong project
  - 2.6. Data Quality, Audit, Metadata và Lineage
  - 2.7. Dashboard và truy vấn phân tích
  - 2.8. Kiểm thử, đánh giá, hạn chế và hướng phát triển
- Phụ lục A - Hướng dẫn chạy hệ thống
- Phụ lục B - Cấu trúc project và mô tả file chính
- Phụ lục C - Danh sách kiểm tra Data Quality và truy vấn minh họa

# Phần I - Lý thuyết

## 1.1. Tổng quan về Data Warehouse

Data Warehouse là hệ thống lưu trữ dữ liệu được thiết kế chủ yếu cho phân tích, báo cáo và hỗ trợ ra quyết định. Khác với cơ sở dữ liệu giao dịch, nơi dữ liệu được tối ưu cho thao tác thêm, sửa, xóa nhanh trong hoạt động hằng ngày, Data Warehouse tối ưu cho truy vấn đọc, tổng hợp và phân tích trên dữ liệu lịch sử.

Trong một doanh nghiệp thương mại điện tử, dữ liệu có thể phát sinh từ nhiều hệ thống: đơn hàng, thanh toán, khách hàng, sản phẩm, nhà bán lẻ, tồn kho, vận chuyển và phản hồi người dùng. Nếu tất cả báo cáo phân tích đều chạy trực tiếp trên hệ thống vận hành, hệ thống vừa dễ bị chậm, vừa khó đảm bảo dữ liệu nhất quán giữa các phòng ban. Data Warehouse giải quyết vấn đề này bằng cách gom dữ liệu về một kho phân tích chung, chuẩn hóa dữ liệu theo mô hình ổn định và cung cấp một nguồn dữ liệu thống nhất.

Các đặc điểm cốt lõi của Data Warehouse gồm:

- **Hướng chủ đề**: dữ liệu được tổ chức theo các chủ đề nghiệp vụ như Sales, Customer, Product thay vì theo từng ứng dụng nhỏ lẻ.
- **Tích hợp**: dữ liệu từ nhiều nguồn được chuẩn hóa về cùng kiểu dữ liệu, quy ước mã, định dạng thời gian và cấu trúc bảng.
- **Biến đổi theo thời gian**: kho dữ liệu thường giữ lịch sử để phân tích xu hướng theo ngày, tháng, quý hoặc năm.
- **Ít thay đổi sau khi nạp**: dữ liệu sau khi được đưa vào kho chủ yếu phục vụ đọc và phân tích, không bị cập nhật liên tục như dữ liệu OLTP.

Lợi ích chính của Data Warehouse là tạo nền tảng đáng tin cậy cho báo cáo, giảm tải cho hệ thống vận hành, hỗ trợ phân tích dữ liệu lịch sử và giúp người dùng ra quyết định dựa trên dữ liệu đã được kiểm soát.

## 1.2. Thiết kế Data Warehouse và mô hình đa chiều

Thiết kế Data Warehouse thường sử dụng dimensional modeling, tức là mô hình hóa dữ liệu theo các sự kiện đo lường và các chiều mô tả. Mục tiêu của mô hình này không phải là chuẩn hóa tối đa như mô hình ERD trong OLTP, mà là giúp truy vấn phân tích dễ viết, dễ hiểu và chạy hiệu quả.

Hai thành phần quan trọng nhất là:

- **Fact table**: lưu các sự kiện nghiệp vụ có thể đo lường được, ví dụ một lần bán hàng, một lượt thanh toán hoặc một lượt giao hàng. Fact table thường chứa các measure như số lượng, giá bán, doanh thu, chiết khấu, thuế, cùng các khóa ngoại trỏ đến dimension.
- **Dimension table**: lưu thông tin mô tả cho sự kiện, ví dụ khách hàng là ai, sản phẩm thuộc danh mục nào, đơn hàng phát sinh ngày nào, thanh toán bằng phương thức gì, giao dịch thuộc khu vực nào.

### 1.2.1. Star Schema

Star Schema là mô hình phổ biến nhất trong Data Warehouse. Một fact table nằm ở trung tâm và liên kết trực tiếp với nhiều dimension table xung quanh. Cấu trúc này trực quan, ít tầng join, phù hợp với báo cáo tổng hợp và truy vấn OLAP.

Ưu điểm của Star Schema:

- Truy vấn đơn giản vì fact table kết nối trực tiếp với các dimension.
- Dễ giải thích với người dùng nghiệp vụ.
- Phù hợp cho dashboard, báo cáo doanh thu, phân tích sản phẩm và phân tích khách hàng.
- Tối ưu cho các câu hỏi kiểu “doanh thu theo thời gian”, “top sản phẩm”, “khách hàng mua nhiều nhất”.

Nhược điểm của Star Schema:

- Một số thông tin mô tả trong dimension có thể bị lặp.
- Khi dimension có phân cấp phức tạp, bảng chiều có thể rộng.
- Nếu mô hình nghiệp vụ thay đổi nhiều, cần kiểm soát cẩn thận để tránh phá vỡ báo cáo cũ.

Trong project này, Star Schema được triển khai ở Gold layer với `dw.fact_sales` làm bảng sự kiện trung tâm. Các bảng chiều gồm `dw.dim_customer`, `dw.dim_product`, `dw.dim_retailer`, `dw.dim_address`, `dw.dim_payment` và `dw.dim_date`.

### 1.2.2. Snowflake Schema và Galaxy Schema

Snowflake Schema là biến thể của Star Schema, trong đó các dimension được chuẩn hóa thành nhiều bảng nhỏ hơn. Ví dụ, dimension sản phẩm có thể tách thành Product, Category, Department. Cách thiết kế này giảm lặp dữ liệu nhưng làm truy vấn phức tạp hơn do cần nhiều phép join.

Galaxy Schema dùng nhiều fact table trong cùng một Data Warehouse, thường dành cho hệ thống lớn cần phân tích nhiều quy trình nghiệp vụ khác nhau. Ví dụ một doanh nghiệp có thể có fact bán hàng, fact tồn kho và fact hoàn trả, cùng dùng chung một số dimension như thời gian, sản phẩm hoặc cửa hàng.

Project hiện tại chỉ tập trung vào một quy trình chính là bán hàng thương mại điện tử, nên Star Schema là lựa chọn phù hợp hơn Galaxy Schema.

### 1.2.3. Granularity, Aggregation và Hierarchy

Granularity là mức chi tiết thấp nhất của một dòng dữ liệu trong fact table. Nếu fact table lưu từng dòng order item, hệ thống có thể drill-down rất chi tiết nhưng số dòng sẽ nhiều hơn. Nếu fact table lưu dữ liệu đã tổng hợp theo ngày hoặc tháng, truy vấn có thể nhanh hơn nhưng mất khả năng phân tích từng giao dịch.

Trong project này, `dw.fact_sales` được thiết kế ở mức order-item sau khi import Olist. Mỗi document Olist được tạo theo dạng `OLIST-{order_id}-{order_item_id}`, vì vậy hệ thống giữ được chi tiết từng mặt hàng trong đơn hàng.

Aggregation là việc tính và lưu sẵn dữ liệu tổng hợp. Project hiện tại chưa tạo các bảng tổng hợp vật lý riêng, nhưng các truy vấn dashboard có thể tính tổng doanh thu, số đơn và top sản phẩm trực tiếp từ `dw.fact_sales`.

Hierarchy là phân cấp trong dimension. Ví dụ dimension thời gian có thể phân tích theo năm, tháng, ngày; dimension địa chỉ có thể phân tích theo tỉnh/thành phố, phường/xã, đường. Các phân cấp này giúp người dùng drill-down hoặc roll-up trong phân tích.

### 1.2.4. Metadata và Lineage

Metadata là dữ liệu mô tả dữ liệu. Trong Data Warehouse, metadata có thể chia thành:

- **Business metadata**: định nghĩa nghiệp vụ như doanh thu, đơn hàng hợp lệ, khách hàng, sản phẩm.
- **Technical metadata**: tên bảng, tên cột, kiểu dữ liệu, khóa chính, khóa ngoại, chỉ mục.
- **Operational metadata**: thông tin vận hành như batch id, thời điểm chạy ETL, số dòng xử lý, trạng thái thành công/thất bại.

Lineage cho biết một dòng dữ liệu trong báo cáo đến từ đâu và đã đi qua những bước nào. Đây là yếu tố quan trọng để debug lỗi, giải thích số liệu và kiểm tra độ tin cậy. Project hiện tại giữ lineage bằng `batch_id`, `silver_id`, `bronze_id` và `mongo_id`, nhờ đó có thể truy ngược một dòng Gold về Silver, Bronze và document MongoDB ban đầu.

## 1.3. Quy trình ETL/ELT

ETL là viết tắt của Extract, Transform, Load:

- **Extract**: trích xuất dữ liệu từ hệ thống nguồn.
- **Transform**: làm sạch, chuẩn hóa, kiểm tra và chuyển đổi dữ liệu.
- **Load**: nạp dữ liệu đã xử lý vào Data Warehouse.

ELT có cùng ba bước nhưng thứ tự khác: dữ liệu được Extract và Load vào kho trước, sau đó Transform bên trong nền tảng lưu trữ. ELT thường phù hợp với cloud warehouse có khả năng xử lý lớn. ETL phù hợp khi cần kiểm soát dữ liệu trước khi đưa vào kho phân tích chính.

Trong project này, hướng triển khai là ETL. Dữ liệu Olist được chuyển thành document MongoDB trước, sau đó pipeline Python trích xuất từ MongoDB vào Bronze, chuẩn hóa vào Silver, nạp vào Gold và chạy Data Quality. Cách làm này giúp thể hiện rõ từng giai đoạn xử lý và dễ kiểm tra kết quả ở từng lớp.

## 1.4. Nền tảng triển khai Data Warehouse

Data Warehouse có thể triển khai bằng nhiều nền tảng khác nhau:

- **RDBMS truyền thống**: PostgreSQL, SQL Server, Oracle. Phù hợp với quy mô vừa, dễ triển khai và dễ học.
- **Cloud warehouse**: BigQuery, Snowflake, Redshift, Azure Synapse. Phù hợp dữ liệu lớn và nhu cầu mở rộng linh hoạt.
- **Open-source OLAP/data platform**: ClickHouse, Hive, Trino/Presto. Phù hợp khi cần tối ưu chi phí hoặc xây dựng nền tảng tự quản.
- **NoSQL source systems**: MongoDB, Cassandra hoặc các hệ thống document/key-value thường đóng vai trò nguồn dữ liệu, không phải lớp phân tích cuối cùng.

Project chọn MongoDB làm source và PostgreSQL làm warehouse. Lý do là MongoDB phù hợp để mô phỏng nguồn vận hành linh hoạt, còn PostgreSQL hỗ trợ tốt SQL, khóa ngoại, ràng buộc, schema, index và mô hình Star Schema.

## 1.5. OLAP và truy vấn phân tích

OLAP là nhóm kỹ thuật xử lý phân tích trực tuyến, cho phép người dùng nhìn dữ liệu theo nhiều chiều. OLAP khác OLTP ở mục tiêu sử dụng:

| Tiêu chí | OLTP | OLAP |
| --- | --- | --- |
| Mục tiêu | Ghi nhận giao dịch vận hành | Phân tích, báo cáo, hỗ trợ quyết định |
| Truy vấn | Ngắn, nhiều thao tác ghi/sửa | Dài hơn, nhiều tổng hợp và join |
| Dữ liệu | Hiện tại, cập nhật liên tục | Lịch sử, đã chuẩn hóa cho phân tích |
| Mô hình | Thường chuẩn hóa | Star Schema, Snowflake, Cube |
| Người dùng | Ứng dụng, nhân viên vận hành | Nhà phân tích, quản lý, BI |

Các thao tác OLAP phổ biến:

- **Roll-up**: tổng hợp dữ liệu lên cấp cao hơn, ví dụ từ ngày lên tháng.
- **Drill-down**: đi sâu từ tổng quan đến chi tiết, ví dụ từ doanh thu tháng xuống doanh thu từng ngày.
- **Slice**: chọn một lát dữ liệu theo một điều kiện, ví dụ chỉ xem năm 2018.
- **Dice**: lọc theo nhiều chiều cùng lúc, ví dụ doanh thu năm 2018 tại một bang và một danh mục sản phẩm.
- **Pivot**: xoay góc nhìn phân tích, ví dụ đổi hàng/cột giữa sản phẩm và thời gian.

Project dùng PostgreSQL theo hướng ROLAP: dữ liệu phân tích được lưu trong các bảng quan hệ, còn truy vấn tổng hợp được viết bằng SQL trên fact và dimension.

## 1.6. Ứng dụng Data Warehouse trong BI và thương mại điện tử

Trong Business Intelligence, Data Warehouse là lớp dữ liệu nền cho báo cáo, dashboard và phân tích tự phục vụ. Người dùng có thể theo dõi doanh thu, sản phẩm bán chạy, hành vi khách hàng, xu hướng thanh toán hoặc hiệu quả nhà bán lẻ mà không phải truy vấn trực tiếp hệ thống vận hành.

Với thương mại điện tử, Data Warehouse đặc biệt hữu ích vì dữ liệu giao dịch có nhiều góc nhìn:

- Thời gian: doanh thu theo ngày, tháng, năm.
- Sản phẩm: danh mục nào bán tốt, sản phẩm nào có doanh thu cao.
- Khách hàng: nhóm khách hàng nào mua nhiều, giá trị đơn hàng trung bình.
- Khu vực: địa phương nào có doanh số cao.
- Thanh toán: phương thức thanh toán nào được sử dụng phổ biến.
- Nhà bán lẻ: seller nào đóng góp doanh thu lớn.

Các phân tích này giúp doanh nghiệp tối ưu danh mục sản phẩm, chiến dịch bán hàng, quản lý tồn kho và trải nghiệm khách hàng.

# Phần II - Thực hành

## 2.1. Bài toán và phạm vi triển khai

Project thực hành xây dựng một pipeline Data Warehouse cho dữ liệu bán hàng thương mại điện tử. Bài toán đặt ra là: dữ liệu đơn hàng ban đầu nằm ở nguồn vận hành, có cấu trúc linh hoạt và chưa tối ưu cho truy vấn phân tích; hệ thống cần chuyển dữ liệu đó sang một kho dữ liệu có mô hình rõ ràng để phục vụ báo cáo.

Mục tiêu triển khai gồm:

- Nạp dữ liệu Olist e-commerce từ CSV local vào MongoDB.
- Trích xuất document MongoDB vào Bronze layer trong PostgreSQL.
- Làm sạch và chuẩn hóa dữ liệu sang Silver layer.
- Ghi lại dữ liệu lỗi vào bảng rejected thay vì bỏ qua im lặng.
- Nạp dữ liệu hợp lệ vào Gold layer theo Star Schema.
- Ghi audit batch cho từng lần chạy ETL.
- Chạy Data Quality checks và lưu kết quả.
- Cung cấp dashboard web đơn giản để quan sát số liệu Gold, batch mới nhất và kết quả DQ.

Phạm vi của project là prototype phục vụ môn học. Hệ thống chạy cục bộ bằng Docker Compose, chưa hướng tới vận hành production với phân quyền phức tạp, scheduler tự động, cloud warehouse hoặc monitoring đầy đủ.

## 2.2. Kiến trúc hệ thống

Kiến trúc hiện tại gồm năm nhóm thành phần:

- **Dữ liệu nguồn Olist CSV**: nằm trong `data/olist/raw`.
- **MongoDB**: lưu collection `landing.orders_raw`, đóng vai trò source system sau khi import.
- **PostgreSQL**: lưu các schema `bronze`, `silver`, `dw`, `etl`, `dq`.
- **ETL runner**: chạy Python pipeline từ MongoDB sang PostgreSQL.
- **Dashboard**: server Python hiển thị Gold metrics, batch audit và DQ results.

Luồng tổng quát:

```text
Olist CSV
  -> etl.import_olist_to_mongo
  -> MongoDB landing.orders_raw
  -> etl.main_etl / etl.etl_legacy.run_pipeline()
  -> bronze.orders_raw
  -> silver.orders_clean + silver.orders_rejected
  -> dw.fact_sales + dimension tables
  -> dq.check_results + etl.batch_run
  -> dashboard
```

Các công nghệ chính:

| Thành phần | Công nghệ | Vai trò |
| --- | --- | --- |
| Source staging | MongoDB 7.0 | Lưu dữ liệu đơn hàng dạng document |
| Warehouse | PostgreSQL 16 | Lưu Bronze/Silver/Gold, audit và DQ |
| ETL | Python, pandas, pymongo, psycopg | Import Olist, transform, load, kiểm tra dữ liệu |
| Runtime | Docker Compose | Khởi chạy MongoDB, PostgreSQL, ETL, dashboard |
| Schema management | SQL migration/Flyway CI | Quản lý thay đổi schema và kiểm thử migration |
| Dashboard | Python HTTP server | Hiển thị số liệu phân tích và trạng thái pipeline |

## 2.3. Dữ liệu nguồn Olist và mô hình document

Dữ liệu nguồn nằm trong thư mục `data/olist/raw`. Các file được pipeline sử dụng trực tiếp gồm:

- `olist_orders_dataset.csv`
- `olist_order_items_dataset.csv`
- `olist_customers_dataset.csv`
- `olist_products_dataset.csv`
- `olist_sellers_dataset.csv`
- `olist_order_payments_dataset.csv`
- `product_category_name_translation.csv`

Hai file `olist_geolocation_dataset.csv` và `olist_order_reviews_dataset.csv` cũng có trong thư mục dữ liệu, nhưng pipeline hiện tại chưa dùng trực tiếp trong luồng ETL chính.

Kiểm tra dữ liệu local cho thấy:

| Chỉ số dữ liệu nguồn | Giá trị |
| --- | ---: |
| Số dòng trong `olist_orders_dataset.csv` | 99.441 |
| Số dòng trong `olist_order_items_dataset.csv` | 112.650 |
| Số dòng order-item có trạng thái `delivered` | 110.197 |
| Số đơn hàng `delivered` duy nhất | 96.478 |
| Thời gian sớm nhất trong dữ liệu delivered | 2016-09-15 12:16:38 |
| Thời gian muộn nhất trong dữ liệu delivered | 2018-08-29 15:00:37 |

Importer `etl.import_olist_to_mongo` join các bảng Olist cần thiết, lọc mặc định `order_status=delivered`, sau đó chuyển mỗi dòng order item thành một document MongoDB. Mã đơn hàng trong document được tạo theo dạng `OLIST-{source_order_id}-{source_order_item_id}` để đảm bảo mỗi dòng order item là một sự kiện bán hàng riêng.

Một document sau import gồm các nhóm thông tin:

- Thông tin đơn hàng: `order_id`, `sold_at`, `quantity`, `price`, `discount`, `tax`.
- Khách hàng: `customer_id`, `customer_name`, `membership`.
- Sản phẩm: `product_id`, `product_name`, `product_category`, `product_brand`.
- Nhà bán lẻ: `retailer_id`, `retailer_name`, `rating`.
- Địa chỉ: `street`, `commune_ward`, `province_city`.
- Thanh toán: `payment_type`, `method_provider`.
- Metadata nguồn: dataset, source order id, source item id, freight value, payment value.

Thiết kế document này giúp MongoDB mô phỏng một nguồn dữ liệu vận hành linh hoạt, trong khi phần phân tích cuối cùng vẫn được chuẩn hóa trong PostgreSQL.

## 2.4. Thiết kế Bronze/Silver/Gold và Star Schema

### 2.4.1. Bronze layer

Bronze layer có bảng chính là `bronze.orders_raw`. Bảng này lưu dữ liệu gần với nguồn nhất:

- `bronze_id`: khóa kỹ thuật trong PostgreSQL.
- `batch_id`: liên kết tới batch ETL.
- `mongo_id`: id document bên MongoDB.
- `payload`: JSONB chứa document nguồn.
- `payload_hash`: hash của payload để hỗ trợ đối chiếu.
- `extracted_at`: thời điểm trích xuất.

Bronze layer giúp hệ thống giữ lại dữ liệu gốc để kiểm tra, debug và tái xử lý khi logic transform thay đổi.

### 2.4.2. Silver layer

Silver layer gồm hai bảng:

- `silver.orders_clean`: lưu các bản ghi hợp lệ đã được ép kiểu và chuẩn hóa thành cột rõ ràng.
- `silver.orders_rejected`: lưu các bản ghi bị loại, kèm lý do reject.

Quá trình làm sạch kiểm tra các điều kiện như:

- `order_id` không được rỗng.
- `sold_at` phải chuyển được sang timestamp.
- `quantity` phải lớn hơn 0.
- `price`, `discount`, `tax` không được âm.
- Các nhóm `customer`, `product`, `retailer`, `address`, `payment` phải tồn tại.
- Các trường bắt buộc như `customer_id`, `product_id`, `retailer_id`, `payment_type` không được thiếu.

Silver layer là nơi dữ liệu bắt đầu có schema ổn định, nhưng vẫn giữ liên kết về Bronze thông qua `bronze_id`, `mongo_id`, `payload_hash` và `batch_id`.

### 2.4.3. Gold layer

Gold layer tương ứng với schema `dw`, được thiết kế theo Star Schema. Bảng trung tâm là `dw.fact_sales`, chứa:

- Khóa nghiệp vụ: `order_id`.
- Measure: `quantity`, `price`, `discount`, `tax`.
- Khóa ngoại tới dimension: `customer_key`, `retailer_key`, `product_key`, `date_key`, `address_key`, `payment_key`.
- Lineage: `batch_id`, `silver_id`.

Các dimension gồm:

| Dimension | Vai trò |
| --- | --- |
| `dw.dim_customer` | Lưu khách hàng, tên, email, điện thoại, membership; hiện hỗ trợ SCD Type 2 cho khách hàng |
| `dw.dim_product` | Lưu sản phẩm, danh mục, thương hiệu, tồn kho |
| `dw.dim_retailer` | Lưu nhà bán lẻ và rating |
| `dw.dim_address` | Lưu địa chỉ/khu vực |
| `dw.dim_payment` | Lưu phương thức thanh toán và provider |
| `dw.dim_date` | Lưu ngày, tháng, năm với `date_key` dạng `YYYYMMDD` |

Mức chi tiết của fact table là một dòng order item đã được giao thành công và đã qua kiểm tra dữ liệu.

### 2.4.4. SCD Type 2 cho khách hàng

Project hiện hỗ trợ Slowly Changing Dimension Type 2 cho `dw.dim_customer`. Bảng này có các cột `valid_from`, `valid_to` và `is_current`. Khi thông tin khách hàng thay đổi, pipeline có thể đóng bản ghi hiện tại và tạo bản ghi mới, thay vì ghi đè toàn bộ lịch sử.

Điểm cần lưu ý là SCD2 hiện mới áp dụng cho customer dimension. Các dimension khác như product hoặc retailer vẫn dùng cơ chế upsert trạng thái mới nhất.

## 2.5. Quy trình ETL trong project

### 2.5.1. Import Olist vào MongoDB

Service `olist-pipeline` trong Docker Compose kiểm tra các CSV bắt buộc, chạy importer và sau đó chạy ETL chính. Importer thực hiện các bước:

1. Đọc các CSV Olist bằng pandas.
2. Join order items với orders, customers, products, sellers, payments và category translation.
3. Lọc mặc định các đơn có trạng thái `delivered`.
4. Tạo document MongoDB tương thích với pipeline hiện có.
5. Validate các trường bắt buộc.
6. Upsert document vào `landing.orders_raw`.

Biến `OLIST_LIMIT` trong `.env` cho phép chạy thử với số lượng nhỏ. Nếu `OLIST_LIMIT=0`, importer xử lý toàn bộ dữ liệu delivered.

### 2.5.2. Tạo batch ETL

Khi chạy `python -m etl.main_etl`, hàm `run_pipeline()` tạo một `batch_id` mới và ghi dòng trạng thái ban đầu vào `etl.batch_run`. Bảng này lưu pipeline name, source database, source collection, thời điểm bắt đầu, trạng thái và các bộ đếm số dòng.

### 2.5.3. Extract vào Bronze

Pipeline đọc toàn bộ document trong MongoDB collection, chuyển document thành JSON, tính hash và insert vào `bronze.orders_raw`. Sau khi hoàn tất, pipeline cập nhật `extracted_count` và `bronze_completed_at` trong `etl.batch_run`.

### 2.5.4. Transform vào Silver

Pipeline đọc các dòng Bronze theo batch, gọi logic `clean_order_payload()` để kiểm tra và chuẩn hóa dữ liệu. Dòng hợp lệ được insert/upsert vào `silver.orders_clean`; dòng lỗi được đưa vào `silver.orders_rejected`.

Sau bước này, batch được cập nhật `silver_accepted_count`, `silver_rejected_count` và `silver_completed_at`.

### 2.5.5. Load vào Gold

Pipeline đọc các dòng `silver.orders_clean` theo batch và nạp vào Star Schema. Các dimension được upsert trước để lấy surrogate key, sau đó fact được insert/upsert vào `dw.fact_sales`.

Với `dw.dim_customer`, pipeline xử lý logic SCD2 bằng cách đóng dòng current nếu thông tin khách hàng thay đổi và tạo dòng current mới. Với các dimension còn lại, pipeline cập nhật theo business key hiện tại.

Sau bước Gold, batch được cập nhật `gold_loaded_count` và `gold_completed_at`.

### 2.5.6. Data Quality và kết thúc batch

Sau khi nạp Gold, pipeline chạy các kiểm tra dữ liệu trong `etl.dq`. Nếu các check mức `error` đều pass, batch được đánh dấu `success`. Nếu có lỗi nghiêm trọng, batch được đánh dấu `failed` và `error_message` được ghi lại.

## 2.6. Data Quality, Audit, Metadata và Lineage

### 2.6.1. Data Quality

Project có 15 kiểm tra Data Quality chia theo 4 nhóm:

| Nhóm | Kiểm tra | Ý nghĩa |
| --- | --- | --- |
| Bronze | `bronze_count_matches_batch_audit` | Số dòng Bronze phải khớp audit |
| Bronze | `mongo_id_unique_within_batch` | Không trùng Mongo id trong cùng batch |
| Bronze | `source_order_id_present` | Payload phải có order id |
| Bronze | `payload_hash_present` | Mỗi payload phải có hash |
| Silver | `bronze_rows_accounted_in_silver` | Mọi dòng Bronze phải được clean hoặc reject |
| Silver | `order_id_unique_within_batch` | Không trùng order id trong batch |
| Silver | `required_fields_not_null` | Các trường bắt buộc không được null/rỗng |
| Silver | `numeric_ranges_valid` | Các số lượng/giá trị tiền phải nằm trong miền hợp lệ |
| Silver | `rejected_rows_review` | Ghi nhận số dòng bị reject ở mức warning |
| Gold | `gold_count_matches_batch_audit` | Số dòng fact phải khớp audit Gold |
| Gold | `fact_rows_have_silver_lineage` | Fact phải giữ `silver_id` |
| Gold | `every_silver_row_loaded_to_fact` | Mọi dòng clean phải được nạp vào fact |
| Gold | `fact_dimension_references_valid` | Khóa dimension của fact phải hợp lệ |
| Reconciliation | `silver_gold_gross_amount_match` | Tổng gross amount giữa Silver và Gold phải khớp |
| Reconciliation | `silver_gold_net_amount_match` | Tổng net amount giữa Silver và Gold phải khớp |

Kết quả mỗi check được lưu vào `dq.check_results` với `status`, `severity`, `checked_count`, `failed_count` và `details`.

### 2.6.2. Audit

Audit chính nằm trong `etl.batch_run`. Bảng này trả lời các câu hỏi vận hành:

- Batch nào chạy gần nhất?
- Pipeline chạy thành công hay thất bại?
- Có bao nhiêu dòng được extract?
- Có bao nhiêu dòng được accept/reject ở Silver?
- Có bao nhiêu dòng được nạp vào Gold?
- Thời gian chạy từ lúc bắt đầu đến khi kết thúc là bao lâu?
- Nếu thất bại, lỗi được ghi lại là gì?

Audit giúp pipeline dễ debug hơn và giúp dashboard hiển thị trạng thái ETL mới nhất.

### 2.6.3. Metadata

Project có metadata ở nhiều lớp:

- Metadata kỹ thuật: schema, table, key, index trong SQL.
- Metadata vận hành: `batch_id`, `started_at`, `finished_at`, count theo từng layer.
- Metadata lineage: `mongo_id`, `payload_hash`, `bronze_id`, `silver_id`, `batch_id`.
- Metadata chất lượng: `check_name`, `severity`, `status`, `details` trong DQ.

Nhờ các metadata này, báo cáo và kiểm thử không chỉ nhìn vào kết quả cuối cùng mà còn hiểu được dữ liệu đã đi qua những bước nào.

### 2.6.4. Lineage

Một dòng trong `dw.fact_sales` có thể truy ngược:

```text
dw.fact_sales.silver_id
  -> silver.orders_clean.silver_id
  -> silver.orders_clean.bronze_id
  -> bronze.orders_raw.bronze_id
  -> bronze.orders_raw.mongo_id / payload
  -> MongoDB landing.orders_raw
```

Khả năng truy vết này giúp giải thích tại sao một giá trị xuất hiện trong báo cáo, đồng thời hỗ trợ kiểm tra khi số liệu dashboard có dấu hiệu bất thường.

## 2.7. Dashboard và truy vấn phân tích

Project có dashboard cục bộ chạy bằng Python HTTP server, được expose ở `http://localhost:8501`. Dashboard đọc trực tiếp từ PostgreSQL và hiển thị:

- Tổng số order trong `dw.fact_sales`.
- Tổng units sold.
- Gross sales và average order value.
- Doanh thu theo ngày.
- Batch ETL mới nhất: status, extracted, accepted, rejected, Gold loaded, elapsed.
- Kết quả Data Quality của batch mới nhất.
- Top products.
- Recent orders.

Dashboard không thay thế một công cụ BI chuyên nghiệp, nhưng đủ để minh họa Data Warehouse phục vụ lớp trình bày phân tích.

Các truy vấn phân tích tiêu biểu:

### Doanh thu theo ngày

```sql
SELECT
    d.full_date,
    COUNT(*) AS orders,
    SUM(f.quantity) AS units,
    SUM((f.price - f.discount + f.tax) * f.quantity) AS net_sales
FROM dw.fact_sales f
JOIN dw.dim_date d ON d.date_key = f.date_key
GROUP BY d.full_date
ORDER BY d.full_date;
```

### Top sản phẩm theo doanh thu

```sql
SELECT
    p.product_name,
    p.product_category,
    COUNT(*) AS order_items,
    SUM(f.quantity) AS units,
    SUM((f.price - f.discount + f.tax) * f.quantity) AS net_sales
FROM dw.fact_sales f
JOIN dw.dim_product p ON p.product_key = f.product_key
GROUP BY p.product_name, p.product_category
ORDER BY net_sales DESC
LIMIT 10;
```

### Doanh thu theo phương thức thanh toán

```sql
SELECT
    pay.payment_type,
    pay.method_provider,
    COUNT(*) AS order_items,
    SUM((f.price - f.discount + f.tax) * f.quantity) AS net_sales
FROM dw.fact_sales f
JOIN dw.dim_payment pay ON pay.payment_key = f.payment_key
GROUP BY pay.payment_type, pay.method_provider
ORDER BY net_sales DESC;
```

### Phân tích theo khu vực

```sql
SELECT
    a.province_city,
    COUNT(*) AS order_items,
    SUM((f.price - f.discount + f.tax) * f.quantity) AS net_sales
FROM dw.fact_sales f
JOIN dw.dim_address a ON a.address_key = f.address_key
GROUP BY a.province_city
ORDER BY net_sales DESC
LIMIT 20;
```

## 2.8. Kiểm thử, đánh giá, hạn chế và hướng phát triển

### 2.8.1. Kiểm thử dữ liệu nguồn

Kiểm tra trên bộ CSV local cho thấy dữ liệu Olist đã có đủ file bắt buộc và có 110.197 dòng order-item delivered. Đây là số dòng kỳ vọng đi vào MongoDB khi chạy full import với `OLIST_LIMIT=0`.

Nếu pipeline chạy full dataset và không phát sinh reject, `extracted_count`, `silver_accepted_count` và `gold_loaded_count` trong `etl.batch_run` nên khớp 110.197. Nếu dùng `OLIST_LIMIT`, các chỉ số này sẽ nhỏ hơn theo giới hạn cấu hình.

### 2.8.2. Kiểm thử schema và migration

Repo có thư mục `db/migration` gồm các migration tạo dimension, fact, audit, Bronze/Silver/Gold, Data Quality, watermark và SCD2 cho customer. Workflow `.github/workflows/flyway-ci.yml` khởi động PostgreSQL tạm và chạy Flyway migration test trên GitHub Actions.

Điều này giúp phát hiện lỗi SQL schema sớm, đặc biệt khi thay đổi bảng, khóa ngoại hoặc ràng buộc dữ liệu.

### 2.8.3. Kiểm thử ETL end-to-end

Luồng chạy end-to-end được kiểm tra qua các bước:

1. Khởi động MongoDB và PostgreSQL.
2. Import Olist CSV vào MongoDB.
3. Chạy ETL từ MongoDB sang PostgreSQL.
4. Kiểm tra `dw.fact_sales`.
5. Kiểm tra `etl.batch_run`.
6. Kiểm tra `dq.check_results`.
7. Truy vết một dòng fact về Silver và Bronze.
8. Mở dashboard để kiểm tra hiển thị.

Các bước kiểm tra này xác nhận pipeline không chỉ chạy được, mà còn có dữ liệu phân tích, audit, DQ và lineage.

### 2.8.4. Kết quả đạt được

Project đã đạt được các mục tiêu chính:

- Có pipeline dữ liệu từ Olist CSV đến MongoDB, rồi sang PostgreSQL.
- Có kiến trúc Bronze/Silver/Gold rõ ràng.
- Có Gold layer theo Star Schema.
- Có audit batch cho từng lần chạy.
- Có 15 Data Quality checks ở Bronze, Silver, Gold và reconciliation.
- Có lineage từ fact về source payload.
- Có dashboard web cục bộ.
- Có migration SQL và workflow kiểm thử migration.
- Có SCD Type 2 cho `dim_customer`.

### 2.8.5. Hạn chế hiện tại

Hệ thống vẫn còn một số giới hạn:

- Dashboard hiện là dashboard cục bộ đơn giản, chưa phải BI platform đầy đủ như Power BI, Superset hoặc Metabase.
- Pipeline chưa có scheduler như Airflow, Prefect hoặc Dagster; việc chạy vẫn chủ yếu qua Docker Compose.
- Có bảng `etl_watermark`, nhưng cơ chế incremental loading/CDC chưa hoàn chỉnh ở mức production.
- SCD Type 2 mới áp dụng cho customer dimension, chưa mở rộng cho product hoặc retailer.
- Chưa có phân quyền, quản lý secret và mã hóa dữ liệu theo chuẩn production.
- Chưa có monitoring/alerting chuyên dụng cho pipeline.
- Hệ thống chạy local bằng Docker Compose, chưa triển khai cloud hoặc hạ tầng phân tán.

### 2.8.6. Hướng phát triển

Các hướng mở rộng phù hợp:

- Tích hợp Airflow/Prefect để lên lịch, retry và giám sát pipeline.
- Hoàn thiện incremental loading bằng watermark hoặc change data capture.
- Mở rộng SCD Type 2 cho product, retailer hoặc address nếu nghiệp vụ cần phân tích lịch sử thay đổi.
- Kết nối dashboard BI chuyên nghiệp để tạo báo cáo tương tác.
- Bổ sung data catalog mô tả bảng, cột, measure, dimension và owner.
- Tăng cường bảo mật: tách user đọc/ghi, dùng secret manager, hạn chế quyền database.
- Triển khai cloud warehouse hoặc hệ phân tích quy mô lớn nếu dữ liệu tăng mạnh.

# Kết luận

Bài tập lớn đã triển khai được một hệ thống Data Warehouse hoàn chỉnh ở mức prototype: dữ liệu được đưa từ nguồn Olist vào MongoDB, xử lý qua ETL, lưu theo các lớp Bronze/Silver/Gold trong PostgreSQL, kiểm soát chất lượng bằng DQ checks, ghi nhận audit batch và phục vụ dashboard phân tích. Hệ thống thể hiện rõ mối liên hệ giữa lý thuyết Data Warehouse và thực hành triển khai: Star Schema giúp truy vấn phân tích dễ hơn, ETL giúp kiểm soát dữ liệu trước khi nạp, còn audit/lineage/DQ giúp kết quả phân tích đáng tin cậy hơn.

Trong phạm vi môn học, project phù hợp để minh họa quy trình xây dựng kho dữ liệu cho thương mại điện tử. Nếu tiếp tục phát triển, nhóm nên ưu tiên orchestration, incremental loading, BI dashboard chuyên nghiệp, bảo mật production và mở rộng SCD để hệ thống tiến gần hơn tới mô hình vận hành thực tế.

# Phụ lục A - Hướng dẫn chạy hệ thống

## A.1. Chuẩn bị môi trường

Yêu cầu:

- Docker Desktop hoặc Docker Engine đang chạy.
- File `.env` được tạo từ `.env.example`.
- Các CSV Olist nằm trong `data/olist/raw`.

Tạo `.env`:

```powershell
Copy-Item .env.example .env
```

## A.2. Chạy sạch từ đầu

Khi muốn reset toàn bộ dữ liệu cũ:

```powershell
docker compose down -v
```

Khởi động các service chính:

```powershell
docker compose up -d postgres mongodb dashboard
```

Import Olist và chạy ETL:

```powershell
docker compose --profile tools run --rm olist-pipeline
```

## A.3. Chạy lại ETL khi MongoDB đã có dữ liệu

```powershell
docker compose run --rm etl
```

## A.4. Kiểm tra fact table

```powershell
docker compose exec postgres psql -U warehouse -d warehouse -c "SELECT order_id, quantity, price, discount, tax, batch_id, silver_id FROM dw.fact_sales ORDER BY loaded_at DESC LIMIT 20;"
```

## A.5. Kiểm tra batch mới nhất

```powershell
docker compose exec postgres psql -U warehouse -d warehouse -c "SELECT status, extracted_count, silver_accepted_count, silver_rejected_count, gold_loaded_count, finished_at - started_at AS elapsed FROM etl.batch_run ORDER BY started_at DESC LIMIT 1;"
```

## A.6. Kiểm tra Data Quality

```powershell
docker compose exec postgres psql -U warehouse -d warehouse -c "SELECT layer, check_name, status, severity, checked_count, failed_count, details FROM dq.check_results WHERE batch_id = (SELECT batch_id FROM etl.batch_run ORDER BY started_at DESC LIMIT 1) ORDER BY layer, check_name;"
```

## A.7. Truy vết Gold về Bronze

```powershell
docker compose exec postgres psql -U warehouse -d warehouse -c "SELECT f.order_id, s.silver_id, b.bronze_id, b.mongo_id, b.payload FROM dw.fact_sales f JOIN silver.orders_clean s ON s.silver_id = f.silver_id JOIN bronze.orders_raw b ON b.bronze_id = s.bronze_id WHERE f.order_id LIKE 'OLIST-%' ORDER BY f.loaded_at DESC LIMIT 1;"
```

## A.8. Mở dashboard

Sau khi service dashboard chạy:

```text
http://localhost:8501
```

# Phụ lục B - Cấu trúc project và mô tả file chính

```text
Data-Warehouse-INT3202E-2/
├── .env.example
├── .github/
│   └── workflows/
│       └── flyway-ci.yml
├── data/
│   └── olist/
│       └── raw/
├── db/
│   ├── migration/
│   └── tests/
├── dashboard/
│   └── app.py
├── etl/
│   ├── import_olist_to_mongo.py
│   ├── main_etl.py
│   ├── etl_legacy.py
│   ├── dq.py
│   ├── extract.py
│   ├── transform.py
│   ├── load.py
│   ├── audit.py
│   └── utils.py
├── docker-compose.yml
├── Dockerfile
├── init.sql
├── mongo-init.js
├── requirements.txt
├── Star Schema.drawio
└── README.md
```

| File/thư mục | Vai trò |
| --- | --- |
| `docker-compose.yml` | Định nghĩa PostgreSQL, MongoDB, ETL, dashboard và `olist-pipeline` |
| `Dockerfile` | Build image Python cho ETL và dashboard |
| `init.sql` | Khởi tạo schema khi PostgreSQL volume mới được tạo |
| `db/migration/` | Chứa migration SQL theo phiên bản |
| `.github/workflows/flyway-ci.yml` | Kiểm thử migration bằng Flyway trên GitHub Actions |
| `mongo-init.js` | Tạo collection và index MongoDB cho `orders_raw` |
| `etl/import_olist_to_mongo.py` | Đọc CSV Olist, join dữ liệu, tạo document và upsert vào MongoDB |
| `etl/main_etl.py` | Entry point chạy pipeline ETL |
| `etl/etl_legacy.py` | Điều phối Bronze, Silver, Gold, audit và DQ |
| `etl/dq.py` | Chứa các kiểm tra Data Quality |
| `dashboard/app.py` | Dashboard web đọc từ PostgreSQL |
| `data/olist/raw/` | Bộ CSV Olist local |
| `Star Schema.drawio` | Sơ đồ mô hình Star Schema |
| `README.md` | Hướng dẫn chạy và mô tả project |

# Phụ lục C - Truy vấn kiểm tra và minh họa OLAP

## C.1. Kiểm tra số dòng theo từng layer

```sql
SELECT 'bronze' AS layer, COUNT(*) FROM bronze.orders_raw
UNION ALL
SELECT 'silver_clean', COUNT(*) FROM silver.orders_clean
UNION ALL
SELECT 'silver_rejected', COUNT(*) FROM silver.orders_rejected
UNION ALL
SELECT 'gold_fact_sales', COUNT(*) FROM dw.fact_sales;
```

## C.2. Kiểm tra batch history

```sql
SELECT
    batch_id,
    status,
    extracted_count,
    silver_accepted_count,
    silver_rejected_count,
    gold_loaded_count,
    started_at,
    finished_at
FROM etl.batch_run
ORDER BY started_at DESC
LIMIT 10;
```

## C.3. Roll-up doanh thu theo tháng

```sql
SELECT
    d.year,
    d.month,
    COUNT(*) AS order_items,
    SUM((f.price - f.discount + f.tax) * f.quantity) AS net_sales
FROM dw.fact_sales f
JOIN dw.dim_date d ON d.date_key = f.date_key
GROUP BY d.year, d.month
ORDER BY d.year, d.month;
```

## C.4. Slice theo một năm

```sql
SELECT
    p.product_category,
    COUNT(*) AS order_items,
    SUM((f.price - f.discount + f.tax) * f.quantity) AS net_sales
FROM dw.fact_sales f
JOIN dw.dim_product p ON p.product_key = f.product_key
JOIN dw.dim_date d ON d.date_key = f.date_key
WHERE d.year = 2018
GROUP BY p.product_category
ORDER BY net_sales DESC;
```

## C.5. Drill-down từ bang/khu vực xuống khách hàng

```sql
SELECT
    a.province_city,
    c.customer_id,
    c.customer_name,
    COUNT(*) AS order_items,
    SUM((f.price - f.discount + f.tax) * f.quantity) AS net_sales
FROM dw.fact_sales f
JOIN dw.dim_address a ON a.address_key = f.address_key
JOIN dw.dim_customer c ON c.customer_key = f.customer_key
GROUP BY a.province_city, c.customer_id, c.customer_name
ORDER BY a.province_city, net_sales DESC;
```

## C.6. Kiểm tra SCD2 customer

```sql
SELECT
    customer_id,
    COUNT(*) FILTER (WHERE is_current) AS current_rows,
    COUNT(*) AS total_versions,
    MIN(valid_from) AS first_seen,
    MAX(COALESCE(valid_to, NOW())) AS last_seen
FROM dw.dim_customer
GROUP BY customer_id
ORDER BY total_versions DESC, customer_id
LIMIT 20;
```
