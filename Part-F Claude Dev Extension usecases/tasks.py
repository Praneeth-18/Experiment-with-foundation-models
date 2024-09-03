
def get_task_by_id(tasks, task_id):
    for task in tasks:
        if task['id'] == task_id:
            return task
    return None

def update_task_status(tasks, task_id, status):
    for task in tasks:
        if task['id'] == task_id:
            task['status'] = status
            return True
    return False

def count_completed_tasks(tasks):
    count = 0
    for task in tasks:
        if task['status'] == 'completed':
            count += 1
    return count
        