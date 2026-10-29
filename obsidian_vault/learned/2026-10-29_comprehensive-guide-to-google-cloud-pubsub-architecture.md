---
type: note
created: 2026-10-29
tags: [pubsub, messaging, google-cloud, architecture, configuration]
source_file: /var/folders/k9/z9mnx0_11vddnq7qh3gbxhb80000gn/T/atenea_uploads/84b66b2a-9b9b-43e8-9d3a-95ca8c417a32.md
---

# Comprehensive Guide to Google Cloud Pub/Sub Architecture

## Core Components and Workflow

### Service Components
- **Publisher**: Creates messages and publishes them to a specific topic.
- **Message**: Data moving through the messaging service.
- **Topic**: Named entity representing a message feed.
- **Schema**: Named entity governing the data format of messages.
- **Subscription**: Named entity representing interest in receiving messages from a topic.
- **Subscriber**: Receives messages on a specified subscription.

### Service Workflow
- Publishers send messages (e.g., Message A and B) to a topic attached to subscriptions and a schema.
- The topic delivers copies of all messages to each attached subscription.
- Subscribers attached to subscriptions receive either a subset or all of the messages depending on the architectural setup.

## Life Cycle and Status of Messages

### Message Flow
- A publisher sends a message to a topic.
- Pub/Sub writes the message to storage and simultaneously delivers it to all attached subscriptions.
- The subscription forwards the message to an attached subscriber.
- The subscriber sends an acknowledgment back to Pub/Sub.
- Pub/Sub deletes the message from storage after at least one subscriber per subscription acknowledges it.

### Message States
- **Acknowledged (acked)**: Processed by the subscriber and confirmed; deleted asynchronously from storage once all subscriptions acknowledge it.
- **Unacknowledged (unacked)**: Not acknowledged within the deadline, leading to redelivery until the retention duration expires.
- **Negatively acknowledged (nacked)**: Explicitly rejected by a subscriber using `modifyAckDeadline` with a value of 0, triggering immediate redelivery based on retry settings.

## Publish and Subscribe Patterns

### Supported Patterns
- **Fan-in (many-to-one)**: Multiple publishers send to a single topic, which uses a single subscription and subscriber to aggregate messages.
- **Load-balanced (many-to-many)**: Multiple publishers send to a single topic connected to a single subscription, distributing non-overlapping subsets of messages across multiple subscribers to scale processing.
- **Fan-out (one-to-many)**: Publishers send to a topic attached to multiple subscriptions, ensuring every subscriber receives the exact same set of messages for parallel data operations.

## Configuration Options and Client Libraries

### Available Options
- Google Cloud console
- Google Cloud CLI
- Cloud Client libraries (high-level)
- REST and RPC APIs (low-level)

### Library Best Practices
- Choose efficient languages for high compute loads, such as Java, C++, and Go.
- Always use the latest version of the client library to access new features and bug fixes.
- Reuse publisher clients instead of creating new instances for every publish request to avoid connection overhead.

## Setup Procedures and Resource Naming

### Setup Steps
- Create or choose a Google Cloud project and enable the Pub/Sub API.
- Acquire required roles, permissions, and create a topic.
- Define and attach an optional schema for message structure validation.
- Configure publisher clients, advanced publishing options, and subscription types.
- Set up subscriber clients to begin receiving and processing messages.

### Naming Conventions
- Format: `projects/project-identifier/collection/ID`
- `collection` must be one of `topics`, `subscriptions`, `schemas`, or `snapshots`.
- `ID` must start with a letter, avoid the prefix `goog`, contain 3 to 255 characters, and use permitted characters (letters, numbers, dashes, underscores, periods, tildes, plus signs, and percent signs).