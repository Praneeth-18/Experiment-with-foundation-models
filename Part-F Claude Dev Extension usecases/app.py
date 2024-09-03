
from flask import Flask, request, jsonify
from models import Task
from tasks import get_task_by_id, update_task_status

app = Flask(__name__)

@app.route('/tasks/<int:task_id>', methods=['GET'])
def get_task(task_id):
    task = Task.query.get(task_id)
    if task:
        return jsonify({'id': task.id, 'title': task.title, 'status': task.status}), 200
    return jsonify({'error': 'Task not found'}), 404

@app.route('/tasks/<int:task_id>', methods=['POST'])
def update_task(task_id):
    task = Task.query.get(task_id)
    if task:
        task.status = request.json.get('status', task.status)
        db.session.commit()
        return jsonify({'message': 'Task updated successfully'}), 200
    return jsonify({'error': 'Task not found'}), 404

if __name__ == '__main__':
    app.run(debug=True)
        