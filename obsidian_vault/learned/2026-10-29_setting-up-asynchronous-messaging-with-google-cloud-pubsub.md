---
type: note
created: 2026-10-29
tags: [google-cloud, pub-sub, python, tutorial, messaging]
source_file: /var/folders/k9/z9mnx0_11vddnq7qh3gbxhb80000gn/T/atenea_uploads/34d70259-ae40-4c88-b51c-472e7ea3a142.md
---

# Setting Up Asynchronous Messaging with Google Cloud Pub/Sub

## Pub/Sub Messaging Overview

Pub/Sub facilitates asynchronous communication by decoupling publishers from subscribers using message topics. This architecture increases system robustness and simplifies development because publishers do not require receivers to be active or available. When a publisher sends a message, the Pub/Sub service ensures delivery to one or more subscribers whenever they become available.

### One-to-Many Architecture

The tutorial implements a one-to-many communication pattern where a single publisher sends a message to a topic, and multiple subscribers receive copies through separate subscriptions. Subscribers can operate independently and start at different times, demonstrating how the service stores messages until retrieval.

## Environment and Prerequisites

### Software Requirements

Development requires Python 3.7 or higher to support the official Pub/Sub Client Libraries. Users must install Python and configure authentication credentials using an IAM service account.

### Project Setup and Code Acquisition

1. Clone the repository containing the Python sample code:
   ```bash
   git clone https://github.com/googleapis/python-pubsub.git
   ```
2. Configure three separate terminal windows for the publisher and two subscribers.
3. Create and activate a Python virtual environment named `pyenv-qs`.
4. Install the upgrade client library package:
   ```bash
   python -m pip install --upgrade google-cloud-pubsub
   ```
5. Set the project ID environment variable and navigate to the quickstart directory.

## Creating Topics and Subscriptions

To manage message flow, create a central topic and attach two pull-based streaming subscriptions.

### Topic Creation

Create the primary message topic named `hello_topic`:
```bash
gcloud pubsub topics create hello_topic
```

### Subscription Creation

Create two StreamingPull subscriptions and attach them to the topic:
```bash
gcloud pubsub subscriptions create sub_one --topic=hello_topic
gcloud pubsub subscriptions create sub_two --topic=hello_topic
```

## Running the Publisher and Subscriber Applications

### Subscriber One Execution

Start the first subscriber in its designated terminal to open a bidirectional streaming connection:
```bash
python sub.py $PROJECT sub_one
```

### Publisher Execution

Start the publisher application to send a "Hello, World!" message:
```bash
python pub.py $PROJECT hello_topic
```
The publisher transmits the message without awareness of active subscriptions. Subscriber 1 receives the message, prints it, and transmits an acknowledgment back to the service, which then removes the message from `sub_one`.

### Subscriber Two Execution

Start the second subscriber after the message has already been published:
```bash
python sub.py $PROJECT sub_two
```
Pub/Sub retains the message within the `sub_two` subscription, allowing Subscriber 2 to receive it despite starting after the publication event.

## Resource Cleanup and Maintenance

To avoid ongoing charges and clear test resources, shut down the infrastructure:

1. Stop all active application processes.
2. Delete the Pub/Sub topic:
   ```bash
   gcloud pubsub topics delete hello_topic
   ```
3. Delete the Pub/Sub subscriptions:
   ```bash
   gcloud pubsub subscriptions delete sub_one
   gcloud pubsub subscriptions delete sub_two
   ```
4. Revoke local authentication credentials:
   ```bash
   gcloud auth application-default revoke
   gcloud auth revoke
   ```