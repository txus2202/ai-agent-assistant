---
type: note
created: 2026-10-29
tags: [google-cloud, pubsub, messaging, console, tutorial]
source_file: /var/folders/k9/z9mnx0_11vddnq7qh3gbxhb80000gn/T/atenea_uploads/ea57b244-c2d8-4584-8c88-abff076a7e38.md
---

# Managing Pub/Sub Topics and Messages in Google Cloud

## Creating a Pub/Sub Topic

### Navigation and Setup
- Access the Pub/Sub page in the Google Cloud console.
- Navigate to the **Topics** section to initiate resource creation.

### Topic Configuration
- Click **Create topic** to open the configuration window.
- Enter `MyTopic` in the **Topic ID** field.
- Retain default values for remaining settings and click **Create** to generate the topic and its default subscription (`MyTopic-sub`).

## Adding a Second Subscription

### Subscription Configuration
- Access the **Pub/Sub subscriptions** page in the Google Cloud console.
- Click **Create subscription** to add a new endpoint.
- Enter `MySub` in the **Subscription ID** field.

### Association and Delivery
- Select `MyTopic` from the **Select a Cloud Pub/Sub topic** drop-down menu.
- Save the configuration by clicking **Create**.
- Pub/Sub will deliver all messages sent to `MyTopic` to both `MySub` and the default subscription `MyTopic-sub`.

## Publishing Messages to a Topic

### Accessing the Topic Messages
- Navigate to the **Pub/Sub topics** page in the Google Cloud console.
- Select the `MyTopic` topic and open its **Messages** tab.
- Click **Publish message** to open the message composition window.

### Sending the Message
- Enter `Hello World` in the **Message body** field.
- Click **Publish** to send the message to the topic.
- Verify the success confirmation message displayed at the bottom of the page.

## Pulling Messages from a Subscription

### Executing a Pull Request
- Go to the **Pub/Sub subscriptions** page in the Google Cloud console.
- Open the **Messages** tab for the target subscription and click **Pull**.
- Review the retrieved message displaying the data `Hello World` and the timestamp.

### Troubleshooting Low Volume Pulls
- Individual pulls for low message volumes may occasionally return zero messages.
- Click **Pull** multiple times to issue subsequent requests if no messages appear immediately.

## Cleaning Up Resources

### Deleting Topics and Subscriptions
- Navigate to the **Topics** page in the Google Cloud console.
- Select the checkbox next to `MyTopic` and click **Delete**.
- Follow the prompts in the confirmation window to permanently remove the topic and its associated subscriptions.

### Alternative Cleanup
- Delete the entire Google Cloud project to remove all associated resources and avoid ongoing charges.