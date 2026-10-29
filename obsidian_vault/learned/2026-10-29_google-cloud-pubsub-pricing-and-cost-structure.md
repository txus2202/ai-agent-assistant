---
type: note
created: 2026-10-29
tags: [google-cloud, pubsub, pricing, documentation]
source_url: https://cloud.google.com/pubsub/pricing?hl=es-419
---

# Google Cloud Pub/Sub Pricing and Cost Structure

## Overview of Google Cloud Pub/Sub
### Purpose of the Service
Google Cloud Pub/Sub is a fully managed real-time messaging service that allows you to send and receive messages between independent applications.

### Pricing Model Basis
Billing for Pub/Sub is usage-based, depending on the volume of data processed, the type of operations performed, and specific routing features utilized.

## Data Volume and Ingestion Costs
### Standard Message Ingestion
Costs are calculated based on the total volume of data published to topics, measured in gigabytes (GB).

### Message Delivery Outflow
Data egress and delivery to subscribers also contribute to the overall bandwidth and data transfer costs.

## Operations and API Calls Pricing
### Metadata and Management Operations
Certain administrative actions, schema validations, and management API calls may incur costs based on request volumes.

### Message Retrieval Operations
Pull and push delivery mechanisms process operations that are metered based on request counts or data throughput.

## Additional Features and Storage
### Message Storage Fees
Retaining unacknowledged messages beyond standard thresholds incurs active storage costs per gigabyte-month.

### Data Routing and Analytics Integration
Advanced features such as message filtering, schemas, and direct streaming to BigQuery or Cloud Storage may carry specific pricing tiers.