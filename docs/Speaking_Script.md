# SpendSight — Presentation Speaking Script & Demo Guide
## Total Time: 12-15 minutes

---

## Slide 1: Title (30 seconds)

"Good [morning/afternoon], my name is Pratham Shah, and today I'm presenting SpendSight — an AI-powered personal expense tracker built entirely on AWS serverless architecture with Google's Gemini Vision AI."

"This project demonstrates how modern cloud services can work together to solve a real-world problem — tracking your spending — without managing a single server."

---

## Slide 2: The Problem (1 minute)

"Let me start with why this project exists."

"If you've ever tried tracking expenses manually, you know the pain. You have to type in every receipt — the store name, the amount, the date. It's tedious, and most people give up after a week."

"Existing apps either require manual entry or use basic OCR that can't handle messy receipts. And if you're sharing a tool with family, there's no data separation — everyone sees everything."

"SpendSight solves all four of these problems."

---

## Slide 3: Our Solution (1 minute)

"Here's how SpendSight works in four steps."

"First, you upload a receipt — just snap a photo or drag and drop. Second, Google's Gemini AI reads the receipt and extracts the vendor name, total amount, date, and even categorizes it as Food, Shopping, or Transportation."

"Third, your expense immediately flows through our analytics pipeline, so your dashboard updates in near-real-time. And fourth, every user signs in with Google, so your data is completely isolated — you only see your own expenses."

---

## Slide 4: Architecture (2 minutes)

"This is the architecture. Everything is serverless — no EC2 instances, no servers to manage."

"The user interacts with a static website hosted on S3. When they upload a receipt, the frontend requests a presigned URL from API Gateway, which triggers a Lambda function. The receipt goes directly to S3, which triggers another Lambda that calls Gemini AI for OCR."

"The extracted data is saved to DynamoDB. From there, DynamoDB Streams automatically triggers a Lambda that writes analytics-ready records to a separate S3 bucket, partitioned by year, month, and day. Athena then queries this data lake for the dashboard."

"The key insight here is that there are two separate data flows — the upload flow is user-facing and fast, while the analytics flow is event-driven and runs in the background."

---

## Slide 5: AWS Services (1 minute)

"We use six core AWS services. S3 serves three purposes — website hosting, receipt storage, and analytics data lake. Lambda runs four separate functions, each with a specific job. API Gateway provides the REST interface."

"DynamoDB stores the expense records with Streams enabled for the analytics pipeline. Athena runs SQL queries directly on S3 without any database setup. And CloudWatch handles all our logging and debugging."

"Every single one of these operates within the AWS free tier for demo usage."

---

## Slide 6: AI Receipt Parsing (2 minutes)

"This is the AI component — and honestly, the most impressive part."

"On the left, you see an actual Starbucks receipt. On the right, the JSON output from Gemini. The AI doesn't just do basic OCR — it understands receipt layouts. It knows 'STARBUCKS #63225' should be cleaned up to just 'Starbucks'. It finds the total amount of $38.02 even with multiple line items. It extracts the date and even categorizes it as Food."

"We use Gemini 2.0 Flash, which is Google's fastest multimodal model. We also enforce JSON mode through the API configuration, so the response is always clean JSON that our Lambda can parse reliably."

"I also implemented retry logic with exponential backoff — if the API returns a 429 rate limit error, the Lambda waits and retries up to three times instead of failing immediately."

---

## Slide 7: Authentication (1 minute)

"For user segmentation, we use Google OAuth 2.0. When a user signs in, we get their email from the JWT token. That email becomes their identity everywhere in the system."

"In DynamoDB, the partition key is USER#email — so Alice's data is physically separate from Bob's. When uploading receipts, they go to a user-specific S3 path. And all analytics queries include a WHERE clause filtering by userId."

"This means two people can use the same website URL and see completely different data."

---

## Slide 8: Data Model (1 minute)

"This is our DynamoDB schema. We use a single-table design with composite keys."

"The partition key is the user's email, and the sort key starts with DATE# followed by the expense date and a timestamp. This design lets us efficiently query all expenses for a specific user within a date range using DynamoDB's between operator."

"We chose DynamoDB over a relational database because it offers millisecond latency, automatic scaling, and the Streams feature that powers our analytics pipeline."

---

## Slide 9: Analytics Pipeline (1.5 minutes)

"This is the analytics pipeline — probably the most architecturally interesting part."

"When a new expense is saved to DynamoDB, Streams captures the INSERT event and triggers our Analytics Writer Lambda. This Lambda transforms the record into a flat JSON row and writes it to S3 with Hive-style partitioning — year equals 2026, month equals 02, day equals 08."

"This partitioning is critical. When Athena runs a query for February 2026, it only reads files in the month=02 folder, not the entire dataset. For production-scale data, this reduces query costs by up to 99%."

"The Analytics Query Lambda then executes Athena SQL and returns the results to the dashboard — monthly trends, category breakdowns, top vendors, and daily spending."

---

## Slide 10: Security & Cost (1 minute)

"On security — every Lambda function has a dedicated IAM role with only the permissions it needs. Receipts are uploaded via presigned URLs, so they go directly to S3 without passing through our API. Google OAuth handles authentication, and user data is isolated at every layer."

"On cost — this runs at effectively zero dollars per month. All AWS services are within free tier limits, and Google Cloud's $300 credit covers the Gemini API usage. Even at scale, the pay-per-use model means costs grow linearly with usage."

---

## Slide 11: Live Demo (2-3 minutes)

**[PREPARATION BEFORE THE DEMO]**

1. Open SpendSight in your browser
2. Have a receipt image ready (the Starbucks receipt works well)
3. Have the DynamoDB console open in another tab

**[DEMO SCRIPT]**

"Let me show you this working."

1. "Here's the SpendSight website, hosted on S3. I'll sign in with Google..." [Click Sign In]
2. "Now I'll upload this Starbucks receipt..." [Upload the receipt]
3. "The progress bar shows it going to S3... now the AI is analyzing it..."
4. "After about 5 seconds, let's refresh..." [Wait and refresh]
5. "And there it is — Starbucks, $38.02, Food category, extracted automatically."
6. "Let me also add a manual expense..." [Add one quickly]
7. "Now if we go to Analytics..." [Click Analytics]
8. "You can see the dashboard updating with our data — spending trend, category breakdown, top vendors."

"If someone else logged in with a different Google account, they would see a completely empty dashboard — their data is fully isolated."

---

## Slide 12: Thank You & Questions

"That's SpendSight — a fully serverless, AI-powered expense tracker with real-time analytics and user segmentation, built entirely on AWS."

"I'm happy to take any questions about the architecture, the AI integration, or the technical decisions."

---

## Common Questions You Might Be Asked

**Q: Why Gemini instead of AWS Textract?**
A: "Textract's AnalyzeExpense API requires a paid AWS plan for activation. Gemini 2.0 Flash is free with Google Cloud credits, has excellent multimodal capabilities, and returns structured JSON directly — which simplified our parsing logic."

**Q: Why not use a traditional database like RDS?**
A: "DynamoDB offers millisecond latency, automatic scaling, and DynamoDB Streams — which enables our entire analytics pipeline. RDS would require provisioning, scaling configuration, and wouldn't have the native change-data-capture feature."

**Q: How would you scale this for production?**
A: "The architecture is already horizontally scalable — Lambda auto-scales, DynamoDB auto-scales, and S3 is virtually unlimited. For production, I'd add AWS Cognito for proper token validation, move from JSON to Parquet format for Athena efficiency, and add AWS Budgets with alerts."

**Q: Is the data secure?**
A: "Yes — S3 encryption at rest, presigned URLs for upload (no data through the API), Google OAuth for authentication, and DynamoDB partition keys for data isolation. For production, I'd add Cognito authorizers on API Gateway for server-side token validation."

**Q: What happens if the Gemini API is down?**
A: "The Lambda has retry logic with exponential backoff — it retries up to 3 times on 429 or 503 errors. If all retries fail, it saves a fallback entry so the receipt isn't lost, and the user can manually correct the data later."

**Q: Why use query parameters instead of headers for userId?**
A: "We initially used a custom X-User-Email header, but it required complex CORS configuration in API Gateway. Query parameters avoid CORS preflight issues entirely while achieving the same functionality. In production, we'd use Cognito tokens validated server-side."
