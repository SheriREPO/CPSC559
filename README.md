## Changes I made to Alex code :
## 1) Client tasks were getting lost (“disappearing”)

* **Bug:** A **non-leader** could receive a message from `task_submission`, then your handler returned early (`if self.id != self.leader_id: return`), but the message still got **ACKed** because of `async with msg.process()` → the task was deleted and the leader never saw it.
* **Fix:** Prevent non-leaders from ever consuming client submissions (leader-only watching).

## 2) Leader-only “watch” on `task_submission`

* **Bug/design flaw:** Using one shared `task_submission` queue risks the wrong consumer grabbing messages, especially during leader transitions.
* **Fix:** Use **per-server submission queues** (`task_submission.<server_id>`) and **bind/unbind only for the leader**:

  * leader binds its queue to routing key `task_submission`
  * stepping down cancels the consumer + unbinds

## 3) “Submit before leader ready” race

* **Bug:** GUI could submit tasks **before a leader exists / before binding happens**, so tasks could be unroutable or delayed.
* **Fix:** Update `submit_task()` to **wait until a leader is elected** (retry loop), then submit.

## 4) No saved completion history

* **Bug:** You only printed `TASK_DONE`; you didn’t store it anywhere to show later.
* **Fix:** Add a `completed_tasks` list and a GUI button to print it.

## 5) Completion history didn’t survive leader changes

* **Bug/design gap:** Only the leader was saving completions; when leadership changed, the new leader didn’t have old history.
* **Fix:** Append to `completed_tasks` on **every server** when `TASK_DONE` arrives (replicated history).

## 6) Confusing/“wrong looking” history due to task ID collisions

* **Bug:** Each leader’s `task_counter` resets, so task IDs repeat across leader changes (e.g., task 1 appears again).
* **Fix:** Make IDs unique across leaders (e.g., `leader_<id>_task_<n>`) or switch to a global-id strategy.


### 7) Added a GUI button to display the leader’s completed-task log

* **Problem:** You had no easy way to view the saved history; it was just scrolling logs.
* **Change:** Added a Tkinter button (e.g., **“Show Completed (Leader)”**) and a handler function that:


## Other things left To do :

RabbitMQ usage:
Bully lets you recover from a **leader** crash, but if **RabbitMQ** is running on one PC it’s a **single point of failure**, so to keep working when that PC goes down you must make RabbitMQ **highly available (cluster/replicated)** or **move election off RabbitMQ** (or host RabbitMQ on **stable always-on infrastructure**).

“Too many tasks” showing up (stale backlog):
* **Bug/ops issue:** Old messages persisted in RabbitMQ (durable queues), so when a new leader binds it can suddenly consume leftover tasks from previous runs.
* **Fix options:** purge/reset queues for clean demos, or make queues non-durable so each run starts clean.

## Notes : How to run the task manager
### Template:
#### Docker
docker run -d --name <container_name> \
  -p <amqp_host_port>:5672 \
  -p <ui_host_port>:15672 \
  rabbitmq:3-management
Command to start docker on local port 15672:
>> docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management

### Set environment
Set environment and install libraries:
I'm using conda env called 'work'
>> conda init
>> source ~/.bash_profile
>> conda activate work

### Dependencies
Install dependencies:
>> pip install aio-pika

### Commands
Command to run gui and start different servers:
>> python3 gui.py

Command to stop:
docker stop rabbitmq

Command to clean:
docker rm rabbitmq