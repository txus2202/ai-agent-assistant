---
type: note
created: 2026-10-29
tags: [google-cloud, websockets, pubsub, compute-engine, nodejs, real-time-data]
source_file: /var/folders/k9/z9mnx0_11vddnq7qh3gbxhb80000gn/T/atenea_uploads/8fa887d5-42e3-43cc-ad1c-5966eba689bb.md
---

# Streaming High-Volume Pub Sub Messages Using WebSockets

## Architecture and Overview

The solution uses WebSockets to handle high-volume data streams from Google Cloud Pub/Sub to a frontend web browser. 
An external message publisher sends data to a Pub/Sub topic, which is consumed by a Compute Engine instance running `pulltop` and `websocketd` to bridge messages to clients.

## Infrastructure Setup

### Compute Engine and Firewall Configuration
- Create a Compute Engine instance named `websocket-server` in the target zone.
- Configure firewall rules to allow TCP traffic on port `8000` for WebSocket connections and port `22` for SSH access.
- Enable the Compute Engine API and Pub/Sub API using the Google Cloud CLI.

### Software Installation
- Install Git, unzip, and Node.js on the Compute Engine instance.
- Download and install the `websocketd` binary tool to wrap command-line output into WebSocket streams.
- Clone the tutorial repository and configure the `pulltop` Node.js script to subscribe to the Pub/Sub topic.

## Message Processing and Buffering

### Local File Buffering
- Capture the output of `pulltop` reading from the public `taxirides-realtime` topic and write it to a local file (`/var/tmp/taxi.json`).
- Using a local file decouples the `websocketd` process from live Pub/Sub streaming, allowing smooth client experiences even if topic throughput fluctuates.

### Frontend Optimization
- High message volumes (up to 2500 messages per second) require careful browser processing to avoid locking up the UI.
- The dashboard calculates real-time aggregate metrics and samples individual ride events on a scheduled interval (e.g., every three seconds) rather than creating DOM elements for every incoming message.

## Dashboard Metrics

- **Last message latency:** Time elapsed between the last observed event timestamp and the browser clock.
- **Active rides:** Number of rides currently in progress, incremented on pickup and decremented on dropoff.
- **Message rate:** Average number of ride events processed per second.
- **Financial and passenger metrics:** Total metered amount, total passengers, average passengers per ride, and average metered amount per passenger.

## Resource Cleanup

### Removing Firewall Rules
- Delete the custom firewall rule allowing traffic on port `8000`.
- Delete the custom SSH firewall rule on port `22` if it was manually created for the project.

### Project Deletion
- Alternatively, shut down the entire Google Cloud project via the Manage Resources page to terminate all billable components and associated resources.