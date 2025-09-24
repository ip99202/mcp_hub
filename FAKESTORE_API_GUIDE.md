# FakeStoreAPI 상품 조회 툴 등록 가이드

## 1. 서버 등록

### 서버 정보
- **서버 이름**: `FakeStore API`
- **Base URL**: `https://fakestoreapi.com`
- **인증**: None (공개 API)
- **기본 헤더**: `{"Accept": "application/json"}`

### 등록 단계
1. MCP Hub Dashboard에서 "Servers" 탭 클릭
2. "+ Add Server" 버튼 클릭
3. 다음 정보 입력:
   - **Server Name**: `FakeStore API`
   - **Base URL**: `https://fakestoreapi.com`
   - **Authentication**: `None`
   - **Default Headers**: `{"Accept": "application/json"}`
   - **Active**: ✅ 체크
4. "Save" 클릭

## 2. 툴 등록

### 2.1 모든 상품 조회 (get_all_products)

**기본 정보**
- **Tool Name**: `get_all_products`
- **Description**: `Retrieve a list of all available products`
- **HTTP Method**: `GET`
- **Path Template**: `/products`

**입력 스키마**
```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

**매핑 설정**
- **Path Mapping**: `{}`
- **Query Mapping**: `{}`
- **Headers Mapping**: `{}`
- **Body Mapping**: `{}`
- **Raw Body Key**: (비워둠)
- **Response Mapping**: `$` (전체 응답)

**등록 단계**
1. "Tools" 탭 클릭
2. "+ Add Tool" 버튼 클릭
3. 위 정보 입력 후 "Save"

### 2.2 특정 상품 조회 (get_product_by_id)

**기본 정보**
- **Tool Name**: `get_product_by_id`
- **Description**: `Retrieve details of a specific product by ID`
- **HTTP Method**: `GET`
- **Path Template**: `/products/{id}`

**입력 스키마**
```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "integer",
      "description": "Product ID"
    }
  },
  "required": ["id"],
  "additionalProperties": false
}
```

**매핑 설정**
- **Path Mapping**: `{"id": "id"}`
- **Query Mapping**: `{}`
- **Headers Mapping**: `{}`
- **Body Mapping**: `{}`
- **Raw Body Key**: (비워둠)
- **Response Mapping**: `$` (전체 응답)

### 2.3 상품 추가 (add_product)

**기본 정보**
- **Tool Name**: `add_product`
- **Description**: `Create a new product`
- **HTTP Method**: `POST`
- **Path Template**: `/products`

**입력 스키마**
```json
{
  "type": "object",
  "properties": {
    "title": {
      "type": "string",
      "description": "Product title"
    },
    "price": {
      "type": "number",
      "description": "Product price"
    },
    "description": {
      "type": "string",
      "description": "Product description"
    },
    "category": {
      "type": "string",
      "description": "Product category"
    },
    "image": {
      "type": "string",
      "format": "uri",
      "description": "Product image URL"
    }
  },
  "required": ["title", "price"],
  "additionalProperties": false
}
```

**매핑 설정**
- **Path Mapping**: `{}`
- **Query Mapping**: `{}`
- **Headers Mapping**: `{}`
- **Body Mapping**: `{"title": "title", "price": "price", "description": "description", "category": "category", "image": "image"}`
- **Raw Body Key**: (비워둠)
- **Response Mapping**: `$` (전체 응답)

### 2.4 상품 수정 (update_product)

**기본 정보**
- **Tool Name**: `update_product`
- **Description**: `Update an existing product by ID`
- **HTTP Method**: `PUT`
- **Path Template**: `/products/{id}`

**입력 스키마**
```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "integer",
      "description": "Product ID to update"
    },
    "title": {
      "type": "string",
      "description": "Updated product title"
    },
    "price": {
      "type": "number",
      "description": "Updated product price"
    },
    "description": {
      "type": "string",
      "description": "Updated product description"
    },
    "category": {
      "type": "string",
      "description": "Updated product category"
    },
    "image": {
      "type": "string",
      "format": "uri",
      "description": "Updated product image URL"
    }
  },
  "required": ["id"],
  "additionalProperties": false
}
```

**매핑 설정**
- **Path Mapping**: `{"id": "id"}`
- **Query Mapping**: `{}`
- **Headers Mapping**: `{}`
- **Body Mapping**: `{"title": "title", "price": "price", "description": "description", "category": "category", "image": "image"}`
- **Raw Body Key**: (비워둠)
- **Response Mapping**: `$` (전체 응답)

### 2.5 상품 삭제 (delete_product)

**기본 정보**
- **Tool Name**: `delete_product`
- **Description**: `Delete a specific product by ID`
- **HTTP Method**: `DELETE`
- **Path Template**: `/products/{id}`

**입력 스키마**
```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "integer",
      "description": "Product ID to delete"
    }
  },
  "required": ["id"],
  "additionalProperties": false
}
```

**매핑 설정**
- **Path Mapping**: `{"id": "id"}`
- **Query Mapping**: `{}`
- **Headers Mapping**: `{}`
- **Body Mapping**: `{}`
- **Raw Body Key**: (비워둠)
- **Response Mapping**: `$` (전체 응답)

## 3. 테스트 예시

### 모든 상품 조회 테스트
```json
{}
```

### 특정 상품 조회 테스트
```json
{
  "id": 1
}
```

### 상품 추가 테스트
```json
{
  "title": "Test Product",
  "price": 29.99,
  "description": "A test product",
  "category": "electronics",
  "image": "https://example.com/image.jpg"
}
```

### 상품 수정 테스트
```json
{
  "id": 1,
  "title": "Updated Product",
  "price": 39.99
}
```

### 상품 삭제 테스트
```json
{
  "id": 1
}
```

## 4. 응답 예시

### 상품 조회 응답
```json
{
  "id": 1,
  "title": "Fjallraven - Foldsack No. 1 Backpack, Fits 15 Laptops",
  "price": 109.95,
  "description": "Your perfect pack for everyday use and walks in the forest. Stash your laptop (up to 15 inches) in the padded sleeve, your everyday",
  "category": "men's clothing",
  "image": "https://fakestoreapi.com/img/81fPKd-2AYL._AC_SL1500_.jpg"
}
```

## 5. 주의사항

1. **ID 필드**: 상품 ID는 정수형이어야 함
2. **가격 필드**: 가격은 숫자형 (float)이어야 함
3. **이미지 URL**: 이미지 필드는 유효한 URL 형식이어야 함
4. **필수 필드**: 상품 추가/수정 시 title과 price는 필수
5. **API 제한**: FakeStoreAPI는 테스트용이므로 실제 데이터 변경사항은 저장되지 않음

## 6. 고급 설정 (선택사항)

### 응답 필터링
특정 필드만 추출하고 싶다면 Response Mapping을 다음과 같이 설정:

- **상품 제목만**: `$.title`
- **가격만**: `$.price`
- **카테고리만**: `$.category`
- **이미지 URL만**: `$.image`

### 에러 처리
API 호출 실패 시 에러 메시지가 SSE 스트림을 통해 전달됩니다.
