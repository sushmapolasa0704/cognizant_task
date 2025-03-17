
'''
Authon: Sushma Polasa

Explanation of Changes for Asynchronous Notifications:
Introduced threading Module:
    Used Python’s threading module to offload the notification sending task to a separate thread.
Created send_notification Function:
    This function simulates sending a notification with a time.sleep(2) delay.
Modified update_task Route:
    Instead of blocking execution, it now starts a new thread to handle the notification asynchronously.

Added SSE end point for streaming task updates.
    Added task_updates_queue.put() in the POST, PUT, and DELETE routes to ensure updates are added to the queue.
The endpoint continuously checks the queue for new updates and streams them to the client in SSE format (data: {...}\n\n).

Keep-Alive Mechanism:
    If no updates are available in the queue for a certain period (e.g., 10 seconds),
the server sends a keep-alive message (:keep-alive\n\n) to prevent the connection from timing out.

'''
from flask import Flask, jsonify, request, Response, stream_with_context
import datetime
import time
import threading
import queue

app = Flask(__name__)

# In-memory task storage
tasks = [
    {'id': 1, 'title': 'Grocery Shopping', 'completed': False, 'due_date': '2024-03-15'},
    {'id': 2, 'title': 'Pay Bills', 'completed': False, 'due_date': '2024-03-20'},
]
next_task_id = 3  # For assigning new task IDs

# Global queue for updating tasks
task_updates_queue = queue.Queue()

# send notification when task is updated
def send_notification(task_id, action):
    time.sleep(2)  # Simulate some work (e.g., sending email)
    print(f"Notification sent for task {task_id} (Action: {action})")


@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    return jsonify(tasks)

@app.route('/api/tasks', methods=['POST'])
def create_task():
    global next_task_id
    data = request.get_json()
    new_task = {
        'id': next_task_id,
        'title': data['title'],
        'completed': False,
        'due_date': data.get('due_date') or datetime.date.today().strftime("%Y-%m-%d")
    }
    next_task_id += 1
    tasks.append(new_task)

    # add the task update to queue
    task_updates_queue.put({'task_id': new_task['id'], 'action': 'created', 'data': new_task})

    # Run the notification in a separate thread 
    notification_thread = threading.Thread(target=send_notification, args=(new_task['id'], 'created'))
    notification_thread.start()

    return jsonify(new_task), 201

@app.route('/api/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    data = request.get_json()
    for task in tasks:
        if task['id'] == task_id:
            task.update(data)  # Update task attributes

            # Add the task update to the queue
            task_updates_queue.put({'task_id': task_id, 'action': 'updated', 'data': task})

            # Run the notification in a separate thread
            notification_thread = threading.Thread(target=send_notification, args=(task_id, 'updated'))
            notification_thread.start()

            return jsonify(task), 200
    return jsonify({'error': 'Task not found'}), 404

@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    for i, task in enumerate(tasks):
        if task['id'] == task_id:
            del tasks[i]

            # Add the task update to the queue
            task_updates_queue.put({'task_id': task_id, 'action': 'deleted'})            

            return jsonify({'message': 'Task deleted'}), 204
    return jsonify({'error': 'Task not found'}), 404

# SSE endpoint to stream task updates
@app.route('/stream')
def stream():
    def generate():
        while True:
            try:
                # Wait for an update in the queue
                update = task_updates_queue.get(timeout=10)
                yield f"data: {update}\n\n"
            except queue.Empty:
                # Send a keep-alive message to prevent connection timeout
                yield ":keep-alive\n\n"

    return Response(stream_with_context(generate()), content_type='text/event-stream')

if __name__ == '__main__':
    app.run(debug=True, threaded=True)


