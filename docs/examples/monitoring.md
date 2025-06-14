# Monitoring Examples

This section provides comprehensive examples of monitoring job execution, tracking progress, and handling job lifecycle events in Molq.

## Basic Job Monitoring

### Simple Status Checking

```python title="basic_monitoring.py"
from typing import Generator
import time
from molq import submit
from molq.submitor import LocalSubmitor, SlurmSubmitor

# Local monitoring
local = submit('local_monitor', 'local')

@local
def monitored_local_job() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['sleep', '30'],
        'job_name': 'test_local',
        'block': False
    }
    return job_id

def monitor_local_job():
    job_id = monitored_local_job()
    print(f"Submitted local job: {job_id}")
    
    submitter = LocalSubmitor({})
    
    while True:
        status = submitter.get_job_status(job_id)
        print(f"Job {job_id} status: {status}")
        
        if status in ['completed', 'failed']:
            break
        
        time.sleep(5)
    
    print("Job monitoring complete")

# SLURM monitoring
slurm = submit('slurm_monitor', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'user'
})

@slurm
def monitored_slurm_job() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['sleep', '60'],
        'job_name': 'test_slurm',
        'cpus_per_task': 1,
        'memory': '1G',
        'time': '00:05:00',
        'block': False
    }
    return job_id

def monitor_slurm_job():
    job_id = monitored_slurm_job()
    print(f"Submitted SLURM job: {job_id}")
    
    submitter = SlurmSubmitor({
        'host': 'cluster.example.com',
        'username': 'user'
    })
    
    while True:
        status = submitter.get_job_status(job_id)
        print(f"Job {job_id} status: {status}")
        
        if status in ['COMPLETED', 'FAILED', 'CANCELLED']:
            break
        
        time.sleep(10)
    
    print("SLURM job monitoring complete")
```

### Advanced Job Information

```python title="detailed_monitoring.py"
from typing import Generator
import time
from datetime import datetime
from molq import submit
from molq.submitor import SlurmSubmitor

slurm = submit('detailed_cluster', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'researcher',
    'partition': 'compute'
})

@slurm
def detailed_job() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'long_computation.py'],
        'job_name': 'detailed_monitoring',
        'cpus_per_task': 4,
        'memory': '16G',
        'time': '02:00:00',
        'output_file': 'detailed_%j.out',
        'error_file': 'detailed_%j.err',
        'block': False
    }
    return job_id

def detailed_monitoring(job_id: int):
    submitter = SlurmSubmitor({
        'host': 'cluster.example.com',
        'username': 'researcher'
    })
    
    print(f"=== Monitoring Job {job_id} ===")
    start_time = datetime.now()
    
    while True:
        try:
            # Get job status
            status = submitter.get_job_status(job_id)
            
            # Get detailed job information
            job_info = submitter.get_job_info(job_id)
            
            current_time = datetime.now()
            elapsed = current_time - start_time
            
            print(f"\n[{current_time.strftime('%H:%M:%S')}] Job {job_id} Update:")
            print(f"  Status: {status}")
            print(f"  Monitoring elapsed: {elapsed}")
            
            if job_info:
                print(f"  Submitted: {job_info.get('submit_time', 'N/A')}")
                print(f"  Started: {job_info.get('start_time', 'N/A')}")
                print(f"  Node(s): {job_info.get('node_list', 'N/A')}")
                print(f"  Partition: {job_info.get('partition', 'N/A')}")
                print(f"  Time limit: {job_info.get('time_limit', 'N/A')}")
                print(f"  Time used: {job_info.get('elapsed_time', 'N/A')}")
                print(f"  CPUs: {job_info.get('num_cpus', 'N/A')}")
                print(f"  Memory: {job_info.get('memory', 'N/A')}")
                
                # Calculate progress (if time information available)
                if job_info.get('time_limit') and job_info.get('elapsed_time'):
                    try:
                        time_limit_sec = parse_time_to_seconds(job_info['time_limit'])
                        elapsed_sec = parse_time_to_seconds(job_info['elapsed_time'])
                        progress = (elapsed_sec / time_limit_sec) * 100
                        print(f"  Progress: {progress:.1f}%")
                    except:
                        pass
            
            if status in ['COMPLETED', 'FAILED', 'CANCELLED', 'TIMEOUT']:
                print(f"\n=== Job {job_id} Final Status: {status} ===")
                if job_info and 'exit_code' in job_info:
                    print(f"Exit Code: {job_info['exit_code']}")
                break
            
            time.sleep(30)  # Check every 30 seconds
            
        except Exception as e:
            print(f"Error monitoring job: {e}")
            time.sleep(60)  # Wait longer on error

def parse_time_to_seconds(time_str):
    """Parse SLURM time format (HH:MM:SS or DD-HH:MM:SS) to seconds"""
    if '-' in time_str:
        days, time_part = time_str.split('-')
        days = int(days)
    else:
        days = 0
        time_part = time_str
    
    h, m, s = map(int, time_part.split(':'))
    return days * 86400 + h * 3600 + m * 60 + s

if __name__ == "__main__":
    job_id = detailed_job()
    detailed_monitoring(job_id)
```

## Queue Monitoring

### System Queue Status

```python title="queue_monitoring.py"
from typing import Generator
from molq.submitor import SlurmSubmitor
import pandas as pd

def monitor_queue():
    """Monitor SLURM queue status"""
    submitter = SlurmSubmitor({
        'host': 'cluster.example.com',
        'username': 'researcher'
    })
    
    print("=== Queue Status ===")
    
    # Get queue information
    queue_info = submitter.get_queue_info()
    
    if queue_info:
        # Convert to DataFrame for better display
        df = pd.DataFrame(queue_info)
        
        print(f"Total jobs in queue: {len(df)}")
        print(f"Running jobs: {len(df[df['status'] == 'RUNNING'])}")
        print(f"Pending jobs: {len(df[df['status'] == 'PENDING'])}")
        
        # Show summary by partition
        if 'partition' in df.columns:
            partition_summary = df.groupby('partition')['status'].value_counts()
            print("\nJobs by partition:")
            print(partition_summary)
        
        # Show your jobs
        user_jobs = df[df['user'] == 'researcher']  # Replace with actual username
        if not user_jobs.empty:
            print(f"\nYour jobs ({len(user_jobs)}):")
            print(user_jobs[['job_id', 'name', 'status', 'time_used', 'nodes']].to_string())
    
    # Get partition information
    partitions = submitter.get_partitions()
    if partitions:
        print("\n=== Partition Status ===")
        for partition in partitions:
            print(f"Partition: {partition['name']}")
            print(f"  State: {partition['state']}")
            print(f"  Nodes: {partition.get('total_nodes', 'N/A')}")
            print(f"  CPUs: {partition.get('total_cpus', 'N/A')}")
            print(f"  Available: {partition.get('available_nodes', 'N/A')}")

def monitor_user_jobs(username: str):
    """Monitor specific user's jobs"""
    submitter = SlurmSubmitor({
        'host': 'cluster.example.com',
        'username': username
    })
    
    queue_info = submitter.get_queue_info()
    user_jobs = [job for job in queue_info if job['user'] == username]
    
    print(f"=== Jobs for {username} ===")
    
    if not user_jobs:
        print("No jobs found")
        return
    
    for job in user_jobs:
        print(f"\nJob {job['job_id']}: {job['name']}")
        print(f"  Status: {job['status']}")
        print(f"  Partition: {job.get('partition', 'N/A')}")
        print(f"  Time: {job.get('time_used', 'N/A')} / {job.get('time_limit', 'N/A')}")
        print(f"  Nodes: {job.get('nodes', 'N/A')}")
        print(f"  CPUs: {job.get('cpus', 'N/A')}")

if __name__ == "__main__":
    monitor_queue()
    print("\n" + "="*50 + "\n")
    monitor_user_jobs('researcher')
```

### Resource Utilization

```python title="resource_monitoring.py"
from typing import Generator
import time
import matplotlib.pyplot as plt
from molq.submitor import SlurmSubmitor

class ResourceMonitor:
    def __init__(self, cluster_config):
        self.submitter = SlurmSubmitor(cluster_config)
        self.monitoring_data = []
    
    def collect_resource_data(self):
        """Collect current resource utilization data"""
        partitions = self.submitter.get_partitions()
        queue_info = self.submitter.get_queue_info()
        
        timestamp = time.time()
        
        for partition in partitions:
            partition_name = partition['name']
            
            # Count jobs in this partition
            partition_jobs = [job for job in queue_info 
                            if job.get('partition') == partition_name]
            
            running_jobs = len([job for job in partition_jobs 
                              if job['status'] == 'RUNNING'])
            pending_jobs = len([job for job in partition_jobs 
                              if job['status'] == 'PENDING'])
            
            # Calculate utilization
            total_nodes = partition.get('total_nodes', 0)
            used_nodes = partition.get('used_nodes', 0)
            utilization = (used_nodes / total_nodes * 100) if total_nodes > 0 else 0
            
            self.monitoring_data.append({
                'timestamp': timestamp,
                'partition': partition_name,
                'running_jobs': running_jobs,
                'pending_jobs': pending_jobs,
                'utilization': utilization,
                'total_nodes': total_nodes,
                'used_nodes': used_nodes
            })
    
    def continuous_monitoring(self, duration_hours=24, interval_minutes=15):
        """Run continuous resource monitoring"""
        print(f"Starting {duration_hours}h monitoring (every {interval_minutes} min)")
        
        end_time = time.time() + (duration_hours * 3600)
        interval_seconds = interval_minutes * 60
        
        while time.time() < end_time:
            try:
                self.collect_resource_data()
                print(f"Collected data at {time.strftime('%H:%M:%S')}")
                time.sleep(interval_seconds)
            except KeyboardInterrupt:
                print("\nMonitoring stopped by user")
                break
            except Exception as e:
                print(f"Error collecting data: {e}")
                time.sleep(interval_seconds)
    
    def plot_utilization(self):
        """Plot resource utilization over time"""
        if not self.monitoring_data:
            print("No monitoring data available")
            return
        
        import pandas as pd
        df = pd.DataFrame(self.monitoring_data)
        
        # Plot utilization by partition
        partitions = df['partition'].unique()
        
        fig, axes = plt.subplots(len(partitions), 1, figsize=(12, 4*len(partitions)))
        if len(partitions) == 1:
            axes = [axes]
        
        for i, partition in enumerate(partitions):
            partition_data = df[df['partition'] == partition]
            
            timestamps = pd.to_datetime(partition_data['timestamp'], unit='s')
            
            axes[i].plot(timestamps, partition_data['utilization'], 
                        label='Node Utilization %', color='blue')
            axes[i].plot(timestamps, partition_data['running_jobs'], 
                        label='Running Jobs', color='green')
            axes[i].plot(timestamps, partition_data['pending_jobs'], 
                        label='Pending Jobs', color='red')
            
            axes[i].set_title(f'Partition: {partition}')
            axes[i].set_ylabel('Count / Percentage')
            axes[i].legend()
            axes[i].grid(True)
        
        plt.xlabel('Time')
        plt.tight_layout()
        plt.savefig('resource_utilization.png', dpi=300, bbox_inches='tight')
        plt.show()

def main():
    monitor = ResourceMonitor({
        'host': 'cluster.example.com',
        'username': 'researcher'
    })
    
    # Collect one-time snapshot
    monitor.collect_resource_data()
    
    # Or run continuous monitoring
    # monitor.continuous_monitoring(duration_hours=2, interval_minutes=5)
    
    # Plot results
    # monitor.plot_utilization()

if __name__ == "__main__":
    main()
```

## Job Lifecycle Monitoring

### Job State Transitions

```python title="lifecycle_monitoring.py"
from typing import Generator
import time
from datetime import datetime
from molq import submit
from molq.submitor import SlurmSubmitor

class JobLifecycleMonitor:
    def __init__(self, submitter):
        self.submitter = submitter
        self.job_history = {}
    
    def track_job(self, job_id: int):
        """Track a job through its lifecycle"""
        print(f"Starting lifecycle tracking for job {job_id}")
        
        self.job_history[job_id] = {
            'states': [],
            'start_tracking': datetime.now()
        }
        
        previous_state = None
        
        while True:
            try:
                current_state = self.submitter.get_job_status(job_id)
                current_time = datetime.now()
                
                # Record state change
                if current_state != previous_state:
                    state_info = {
                        'state': current_state,
                        'timestamp': current_time,
                        'duration_in_previous': None
                    }
                    
                    # Calculate duration in previous state
                    if previous_state and self.job_history[job_id]['states']:
                        last_change = self.job_history[job_id]['states'][-1]['timestamp']
                        duration = current_time - last_change
                        state_info['duration_in_previous'] = duration.total_seconds()
                    
                    self.job_history[job_id]['states'].append(state_info)
                    
                    print(f"[{current_time.strftime('%H:%M:%S')}] Job {job_id}: {previous_state} → {current_state}")
                    
                    if state_info['duration_in_previous']:
                        print(f"  Time in {previous_state}: {duration}")
                
                previous_state = current_state
                
                # Check if job is finished
                if current_state in ['COMPLETED', 'FAILED', 'CANCELLED', 'TIMEOUT']:
                    total_duration = current_time - self.job_history[job_id]['start_tracking']
                    print(f"\n=== Job {job_id} Lifecycle Complete ===")
                    print(f"Total tracking time: {total_duration}")
                    self.print_lifecycle_summary(job_id)
                    break
                
                time.sleep(15)  # Check every 15 seconds
                
            except Exception as e:
                print(f"Error tracking job {job_id}: {e}")
                time.sleep(30)
    
    def print_lifecycle_summary(self, job_id: int):
        """Print summary of job lifecycle"""
        if job_id not in self.job_history:
            return
        
        history = self.job_history[job_id]
        states = history['states']
        
        print(f"\nJob {job_id} State Transitions:")
        print("-" * 40)
        
        for i, state_info in enumerate(states):
            timestamp = state_info['timestamp'].strftime('%H:%M:%S')
            state = state_info['state']
            
            print(f"{i+1}. {timestamp} - {state}")
            
            if state_info['duration_in_previous']:
                duration = state_info['duration_in_previous']
                print(f"   Duration in previous state: {duration:.0f}s")
        
        # Calculate time in each state
        print(f"\nTime spent in each state:")
        print("-" * 30)
        
        for i, state_info in enumerate(states):
            state = state_info['state']
            
            if i < len(states) - 1:
                # Not the last state
                next_timestamp = states[i + 1]['timestamp']
                duration = (next_timestamp - state_info['timestamp']).total_seconds()
                print(f"{state}: {duration:.0f}s")
            else:
                # Last state - calculate to now
                duration = (datetime.now() - state_info['timestamp']).total_seconds()
                print(f"{state}: {duration:.0f}s (final state)")

# Example usage
slurm = submit('lifecycle_cluster', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'researcher',
    'partition': 'compute'
})

@slurm
def tracked_job() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'sample_computation.py'],
        'job_name': 'lifecycle_test',
        'cpus_per_task': 2,
        'memory': '8G',
        'time': '01:00:00',
        'block': False
    }
    return job_id

def main():
    # Submit job
    job_id = tracked_job()
    print(f"Submitted job for lifecycle tracking: {job_id}")
    
    # Track lifecycle
    submitter = SlurmSubmitor({
        'host': 'cluster.example.com',
        'username': 'researcher'
    })
    
    monitor = JobLifecycleMonitor(submitter)
    monitor.track_job(job_id)

if __name__ == "__main__":
    main()
```

## Batch Job Monitoring

### Array Job Monitoring

```python title="array_monitoring.py"
from typing import Generator
import time
from collections import defaultdict
from molq import submit
from molq.submitor import SlurmSubmitor

slurm = submit('array_cluster', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'researcher',
    'partition': 'compute'
})

@slurm
def parameter_array_job() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'parameter_study.py', '--param-id', '$SLURM_ARRAY_TASK_ID'],
        'job_name': 'param_array',
        'array': '1-20%5',  # 20 jobs, max 5 concurrent
        'cpus_per_task': 2,
        'memory': '4G',
        'time': '00:30:00',
        'output_file': 'param_%A_%a.out',
        'error_file': 'param_%A_%a.err',
        'block': False
    }
    return job_id

class ArrayJobMonitor:
    def __init__(self, submitter):
        self.submitter = submitter
    
    def monitor_array_job(self, array_job_id: int):
        """Monitor a SLURM job array"""
        print(f"Monitoring array job {array_job_id}")
        
        # Get all array tasks
        array_tasks = self.get_array_tasks(array_job_id)
        
        if not array_tasks:
            print(f"No array tasks found for job {array_job_id}")
            return
        
        print(f"Found {len(array_tasks)} array tasks")
        
        completed_tasks = set()
        
        while len(completed_tasks) < len(array_tasks):
            # Get current status of all tasks
            task_status = defaultdict(list)
            
            for task_id in array_tasks:
                full_job_id = f"{array_job_id}_{task_id}"
                try:
                    status = self.submitter.get_job_status(full_job_id)
                    task_status[status].append(task_id)
                    
                    if status in ['COMPLETED', 'FAILED', 'CANCELLED']:
                        completed_tasks.add(task_id)
                        
                except Exception as e:
                    print(f"Error checking task {task_id}: {e}")
            
            # Print status summary
            print(f"\n=== Array Job {array_job_id} Status ===")
            total_tasks = len(array_tasks)
            completed = len(completed_tasks)
            remaining = total_tasks - completed
            
            print(f"Progress: {completed}/{total_tasks} ({completed/total_tasks*100:.1f}%)")
            print(f"Remaining: {remaining}")
            
            for status, tasks in task_status.items():
                print(f"{status}: {len(tasks)} tasks")
                if len(tasks) <= 10:  # Show task IDs if not too many
                    print(f"  Tasks: {sorted(tasks)}")
            
            if completed_tasks == set(array_tasks):
                print("All array tasks completed!")
                break
            
            time.sleep(30)
        
        # Final summary
        self.print_array_summary(array_job_id, array_tasks)
    
    def get_array_tasks(self, array_job_id: int):
        """Get list of array task IDs"""
        # This would need to be implemented based on SLURM's squeue output
        # For now, return a sample list
        return list(range(1, 21))  # Assuming tasks 1-20
    
    def print_array_summary(self, array_job_id: int, array_tasks: list):
        """Print final summary of array job"""
        print(f"\n=== Final Summary for Array Job {array_job_id} ===")
        
        final_status = defaultdict(list)
        
        for task_id in array_tasks:
            full_job_id = f"{array_job_id}_{task_id}"
            try:
                status = self.submitter.get_job_status(full_job_id)
                final_status[status].append(task_id)
            except:
                final_status['UNKNOWN'].append(task_id)
        
        for status, tasks in final_status.items():
            print(f"{status}: {len(tasks)} tasks")
            if status == 'FAILED' and tasks:
                print(f"  Failed tasks: {sorted(tasks)}")
        
        success_rate = len(final_status['COMPLETED']) / len(array_tasks) * 100
        print(f"Success rate: {success_rate:.1f}%")

def main():
    # Submit array job
    array_job_id = parameter_array_job()
    print(f"Submitted array job: {array_job_id}")
    
    # Monitor array job
    submitter = SlurmSubmitor({
        'host': 'cluster.example.com',
        'username': 'researcher'
    })
    
    monitor = ArrayJobMonitor(submitter)
    monitor.monitor_array_job(array_job_id)

if __name__ == "__main__":
    main()
```

## Real-time Notifications

### Email Notifications

```python title="email_notifications.py"
from typing import Generator
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from molq import submit
from molq.submitor import SlurmSubmitor

class JobNotifier:
    def __init__(self, smtp_config):
        self.smtp_config = smtp_config
    
    def send_notification(self, subject: str, message: str, to_email: str):
        """Send email notification"""
        try:
            msg = MimeMultipart()
            msg['From'] = self.smtp_config['from_email']
            msg['To'] = to_email
            msg['Subject'] = subject
            
            msg.attach(MimeText(message, 'plain'))
            
            server = smtplib.SMTP(self.smtp_config['smtp_server'], self.smtp_config['port'])
            server.starttls()
            server.login(self.smtp_config['username'], self.smtp_config['password'])
            server.send_message(msg)
            server.quit()
            
            print(f"Notification sent: {subject}")
            
        except Exception as e:
            print(f"Failed to send notification: {e}")
    
    def monitor_with_notifications(self, job_id: int, user_email: str):
        """Monitor job and send notifications on state changes"""
        submitter = SlurmSubmitor({
            'host': 'cluster.example.com',
            'username': 'researcher'
        })
        
        previous_status = None
        
        while True:
            try:
                current_status = submitter.get_job_status(job_id)
                
                if current_status != previous_status and previous_status is not None:
                    # Status changed - send notification
                    subject = f"Job {job_id} Status Update"
                    message = f"""
Job {job_id} status changed:
{previous_status} → {current_status}

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                    """
                    
                    self.send_notification(subject, message, user_email)
                
                previous_status = current_status
                
                if current_status in ['COMPLETED', 'FAILED', 'CANCELLED']:
                    # Final notification
                    job_info = submitter.get_job_info(job_id)
                    
                    subject = f"Job {job_id} Completed - {current_status}"
                    message = f"""
Job {job_id} has finished with status: {current_status}

Job Details:
- Name: {job_info.get('name', 'N/A')}
- Start Time: {job_info.get('start_time', 'N/A')}
- End Time: {job_info.get('end_time', 'N/A')}
- Elapsed Time: {job_info.get('elapsed_time', 'N/A')}
- Exit Code: {job_info.get('exit_code', 'N/A')}
- Node(s): {job_info.get('node_list', 'N/A')}

Check your output files for results.
                    """
                    
                    self.send_notification(subject, message, user_email)
                    break
                
                time.sleep(60)  # Check every minute
                
            except Exception as e:
                print(f"Error monitoring job {job_id}: {e}")
                time.sleep(300)  # Wait 5 minutes on error

# Example usage
slurm = submit('notify_cluster', 'slurm', {
    'host': 'cluster.example.com',
    'username': 'researcher',
    'partition': 'compute'
})

@slurm
def notified_job() -> Generator[dict, int, int]:
    job_id = yield {
        'cmd': ['python', 'long_analysis.py'],
        'job_name': 'notified_analysis',
        'cpus_per_task': 8,
        'memory': '32G',
        'time': '04:00:00',
        'mail_type': 'END,FAIL',  # SLURM built-in notifications
        'mail_user': 'researcher@university.edu',
        'block': False
    }
    return job_id

def main():
    # SMTP configuration (use your email provider's settings)
    smtp_config = {
        'smtp_server': 'smtp.gmail.com',
        'port': 587,
        'username': 'your-email@gmail.com',
        'password': 'your-app-password',
        'from_email': 'your-email@gmail.com'
    }
    
    notifier = JobNotifier(smtp_config)
    
    # Submit job
    job_id = notified_job()
    print(f"Submitted job: {job_id}")
    
    # Monitor with notifications
    notifier.monitor_with_notifications(job_id, 'researcher@university.edu')

if __name__ == "__main__":
    main()
```

### Slack Notifications

```python title="slack_notifications.py"
from typing import Generator
import requests
import json
from datetime import datetime
from molq import submit
from molq.submitor import SlurmSubmitor

class SlackNotifier:
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url
    
    def send_slack_message(self, message: str, channel: str = None):
        """Send message to Slack"""
        payload = {
            'text': message,
            'username': 'Molq Job Monitor',
            'icon_emoji': ':robot_face:'
        }
        
        if channel:
            payload['channel'] = channel
        
        try:
            response = requests.post(
                self.webhook_url,
                data=json.dumps(payload),
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                print("Slack notification sent successfully")
            else:
                print(f"Failed to send Slack notification: {response.status_code}")
                
        except Exception as e:
            print(f"Error sending Slack notification: {e}")
    
    def format_job_status_message(self, job_id: int, status: str, job_info: dict = None):
        """Format job status message for Slack"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if status in ['COMPLETED']:
            emoji = ':white_check_mark:'
        elif status in ['FAILED', 'CANCELLED']:
            emoji = ':x:'
        elif status in ['RUNNING']:
            emoji = ':arrow_forward:'
        else:
            emoji = ':hourglass_flowing_sand:'
        
        message = f"{emoji} *Job {job_id}* - {status}\n"
        message += f"Time: {timestamp}\n"
        
        if job_info:
            if job_info.get('name'):
                message += f"Name: {job_info['name']}\n"
            if job_info.get('node_list'):
                message += f"Node(s): {job_info['node_list']}\n"
            if job_info.get('elapsed_time'):
                message += f"Runtime: {job_info['elapsed_time']}\n"
        
        return message
    
    def monitor_with_slack(self, job_id: int, channel: str = None):
        """Monitor job and send Slack notifications"""
        submitter = SlurmSubmitor({
            'host': 'cluster.example.com',
            'username': 'researcher'
        })
        
        # Send initial notification
        initial_message = f":rocket: Started monitoring job {job_id}"
        self.send_slack_message(initial_message, channel)
        
        previous_status = None
        
        while True:
            try:
                current_status = submitter.get_job_status(job_id)
                job_info = submitter.get_job_info(job_id) if current_status != 'PENDING' else {}
                
                # Send notification on status change
                if current_status != previous_status and previous_status is not None:
                    message = self.format_job_status_message(job_id, current_status, job_info)
                    self.send_slack_message(message, channel)
                
                previous_status = current_status
                
                # Final status
                if current_status in ['COMPLETED', 'FAILED', 'CANCELLED']:
                    break
                
                time.sleep(60)
                
            except Exception as e:
                error_message = f":warning: Error monitoring job {job_id}: {str(e)}"
                self.send_slack_message(error_message, channel)
                time.sleep(300)

# Dashboard for multiple jobs
class JobDashboard:
    def __init__(self, slack_notifier):
        self.slack_notifier = slack_notifier
        self.active_jobs = {}
    
    def add_job(self, job_id: int, description: str = ""):
        """Add job to monitoring dashboard"""
        self.active_jobs[job_id] = {
            'description': description,
            'start_time': datetime.now(),
            'last_status': None
        }
    
    def send_dashboard_update(self, channel: str = None):
        """Send dashboard update to Slack"""
        if not self.active_jobs:
            return
        
        submitter = SlurmSubmitor({
            'host': 'cluster.example.com',
            'username': 'researcher'
        })
        
        message = ":bar_chart: *Job Dashboard Update*\n"
        message += "-" * 30 + "\n"
        
        for job_id, job_data in self.active_jobs.items():
            try:
                status = submitter.get_job_status(job_id)
                elapsed = datetime.now() - job_data['start_time']
                
                status_emoji = {
                    'COMPLETED': ':white_check_mark:',
                    'RUNNING': ':arrow_forward:',
                    'PENDING': ':hourglass:',
                    'FAILED': ':x:',
                    'CANCELLED': ':stop_sign:'
                }.get(status, ':question:')
                
                message += f"{status_emoji} Job {job_id} ({status})\n"
                if job_data['description']:
                    message += f"  {job_data['description']}\n"
                message += f"  Runtime: {elapsed}\n\n"
                
            except Exception as e:
                message += f":warning: Job {job_id} - Error: {str(e)}\n\n"
        
        self.slack_notifier.send_slack_message(message, channel)

# Example usage
def main():
    # Initialize Slack notifier with webhook URL
    slack_webhook = "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK"
    notifier = SlackNotifier(slack_webhook)
    
    # Submit multiple jobs
    slurm = submit('slack_cluster', 'slurm', {
        'host': 'cluster.example.com',
        'username': 'researcher',
        'partition': 'compute'
    })
    
    @slurm
    def analysis_job(job_name: str) -> Generator[dict, int, int]:
        job_id = yield {
            'cmd': ['python', 'analysis.py', '--job-name', job_name],
            'job_name': job_name,
            'cpus_per_task': 4,
            'memory': '16G',
            'time': '02:00:00',
            'block': False
        }
        return job_id
    
    # Create dashboard
    dashboard = JobDashboard(notifier)
    
    # Submit and track multiple jobs
    jobs = ['preprocessing', 'training', 'evaluation']
    
    for job_name in jobs:
        job_id = analysis_job(job_name)
        dashboard.add_job(job_id, f"ML Pipeline - {job_name}")
        print(f"Submitted {job_name}: {job_id}")
    
    # Send periodic dashboard updates
    import threading
    
    def periodic_updates():
        while True:
            dashboard.send_dashboard_update('#ml-jobs')
            time.sleep(600)  # Every 10 minutes
    
    update_thread = threading.Thread(target=periodic_updates, daemon=True)
    update_thread.start()
    
    # Monitor individual job
    job_id = analysis_job("detailed_analysis")
    notifier.monitor_with_slack(job_id, '#job-alerts')

if __name__ == "__main__":
    main()
```

## Performance Monitoring

### Resource Usage Tracking

```python title="performance_monitoring.py"
from typing import Generator
import time
import json
from datetime import datetime
from molq.submitor import SlurmSubmitor

class PerformanceMonitor:
    def __init__(self, submitter):
        self.submitter = submitter
        self.performance_data = {}
    
    def track_job_performance(self, job_id: int, interval: int = 60):
        """Track detailed performance metrics for a job"""
        print(f"Starting performance tracking for job {job_id}")
        
        self.performance_data[job_id] = {
            'samples': [],
            'start_time': datetime.now()
        }
        
        while True:
            try:
                status = self.submitter.get_job_status(job_id)
                
                if status == 'RUNNING':
                    # Collect performance metrics
                    job_info = self.submitter.get_job_info(job_id)
                    
                    sample = {
                        'timestamp': datetime.now().isoformat(),
                        'cpu_utilization': self.get_cpu_utilization(job_id),
                        'memory_usage': self.get_memory_usage(job_id),
                        'io_stats': self.get_io_stats(job_id),
                        'elapsed_time': job_info.get('elapsed_time', '0:00:00')
                    }
                    
                    self.performance_data[job_id]['samples'].append(sample)
                    
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Job {job_id} Performance:")
                    print(f"  CPU: {sample['cpu_utilization']:.1f}%")
                    print(f"  Memory: {sample['memory_usage']:.1f} GB")
                    print(f"  Elapsed: {sample['elapsed_time']}")
                
                elif status in ['COMPLETED', 'FAILED', 'CANCELLED']:
                    print(f"Job {job_id} finished with status: {status}")
                    self.save_performance_data(job_id)
                    break
                
                time.sleep(interval)
                
            except Exception as e:
                print(f"Error tracking performance: {e}")
                time.sleep(interval)
    
    def get_cpu_utilization(self, job_id: int) -> float:
        """Get CPU utilization for the job (mock implementation)"""
        # In a real implementation, this would query SLURM or system metrics
        import random
        return random.uniform(60, 95)  # Mock CPU usage
    
    def get_memory_usage(self, job_id: int) -> float:
        """Get memory usage for the job (mock implementation)"""
        # In a real implementation, this would query actual memory usage
        import random
        return random.uniform(8, 32)  # Mock memory usage in GB
    
    def get_io_stats(self, job_id: int) -> dict:
        """Get I/O statistics for the job (mock implementation)"""
        import random
        return {
            'read_mb_per_sec': random.uniform(10, 100),
            'write_mb_per_sec': random.uniform(5, 50)
        }
    
    def save_performance_data(self, job_id: int):
        """Save performance data to file"""
        filename = f"performance_job_{job_id}.json"
        
        with open(filename, 'w') as f:
            json.dump(self.performance_data[job_id], f, indent=2)
        
        print(f"Performance data saved to {filename}")
    
    def generate_performance_report(self, job_id: int):
        """Generate performance summary report"""
        if job_id not in self.performance_data:
            print(f"No performance data for job {job_id}")
            return
        
        data = self.performance_data[job_id]
        samples = data['samples']
        
        if not samples:
            print("No performance samples collected")
            return
        
        # Calculate statistics
        cpu_values = [s['cpu_utilization'] for s in samples]
        memory_values = [s['memory_usage'] for s in samples]
        
        print(f"\n=== Performance Report for Job {job_id} ===")
        print(f"Monitoring duration: {len(samples)} samples")
        print(f"CPU Utilization:")
        print(f"  Average: {sum(cpu_values)/len(cpu_values):.1f}%")
        print(f"  Min: {min(cpu_values):.1f}%")
        print(f"  Max: {max(cpu_values):.1f}%")
        
        print(f"Memory Usage:")
        print(f"  Average: {sum(memory_values)/len(memory_values):.1f} GB")
        print(f"  Min: {min(memory_values):.1f} GB")
        print(f"  Max: {max(memory_values):.1f} GB")
        
        # Identify performance issues
        avg_cpu = sum(cpu_values) / len(cpu_values)
        max_memory = max(memory_values)
        
        print(f"\nPerformance Analysis:")
        if avg_cpu < 50:
            print("⚠️  Low CPU utilization - job may be I/O bound")
        elif avg_cpu > 90:
            print("✅ High CPU utilization - good compute efficiency")
        
        if max_memory > 24:  # Assuming 32GB limit
            print("⚠️  High memory usage - monitor for memory leaks")

def main():
    submitter = SlurmSubmitor({
        'host': 'cluster.example.com',
        'username': 'researcher'
    })
    
    monitor = PerformanceMonitor(submitter)
    
    # Example job ID (replace with actual job)
    job_id = 12345
    
    # Track performance
    monitor.track_job_performance(job_id, interval=30)  # Check every 30 seconds
    
    # Generate report
    monitor.generate_performance_report(job_id)

if __name__ == "__main__":
    main()
```

## Web Dashboard

### Simple Web Interface

```python title="web_dashboard.py"
from typing import Generator
from flask import Flask, render_template, jsonify
import json
import threading
import time
from molq.submitor import SlurmSubmitor

app = Flask(__name__)

class WebDashboard:
    def __init__(self):
        self.submitter = SlurmSubmitor({
            'host': 'cluster.example.com',
            'username': 'researcher'
        })
        self.job_data = {}
        self.update_thread = None
        self.running = False
    
    def start_monitoring(self, job_ids: list):
        """Start monitoring jobs in background thread"""
        self.job_data = {job_id: {} for job_id in job_ids}
        self.running = True
        
        self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.update_thread.start()
    
    def _update_loop(self):
        """Background loop to update job data"""
        while self.running:
            for job_id in self.job_data.keys():
                try:
                    status = self.submitter.get_job_status(job_id)
                    job_info = self.submitter.get_job_info(job_id)
                    
                    self.job_data[job_id] = {
                        'status': status,
                        'info': job_info,
                        'last_update': time.time()
                    }
                    
                except Exception as e:
                    self.job_data[job_id]['error'] = str(e)
            
            time.sleep(30)  # Update every 30 seconds
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self.running = False

# Global dashboard instance
dashboard = WebDashboard()

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/api/jobs')
def api_jobs():
    """API endpoint for job data"""
    return jsonify(dashboard.job_data)

@app.route('/api/queue')
def api_queue():
    """API endpoint for queue information"""
    try:
        queue_info = dashboard.submitter.get_queue_info()
        return jsonify(queue_info)
    except Exception as e:
        return jsonify({'error': str(e)})

# HTML template (save as templates/dashboard.html)
dashboard_html = """
<!DOCTYPE html>
<html>
<head>
    <title>Molq Job Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .job-card { 
            border: 1px solid #ddd; 
            padding: 15px; 
            margin: 10px; 
            border-radius: 5px; 
        }
        .status-running { background-color: #e7f3ff; }
        .status-completed { background-color: #e7ffe7; }
        .status-failed { background-color: #ffe7e7; }
        .status-pending { background-color: #fff3e0; }
        .refresh-btn { 
            padding: 10px 20px; 
            background-color: #007bff; 
            color: white; 
            border: none; 
            border-radius: 5px; 
            cursor: pointer; 
        }
    </style>
</head>
<body>
    <h1>Molq Job Dashboard</h1>
    
    <button class="refresh-btn" onclick="refreshData()">Refresh</button>
    
    <div id="job-container">
        <!-- Jobs will be populated here -->
    </div>
    
    <h2>Queue Status</h2>
    <div id="queue-container">
        <!-- Queue info will be populated here -->
    </div>
    
    <script>
        function refreshData() {
            // Fetch job data
            fetch('/api/jobs')
                .then(response => response.json())
                .then(data => updateJobs(data));
            
            // Fetch queue data
            fetch('/api/queue')
                .then(response => response.json())
                .then(data => updateQueue(data));
        }
        
        function updateJobs(jobData) {
            const container = document.getElementById('job-container');
            container.innerHTML = '';
            
            for (const [jobId, data] of Object.entries(jobData)) {
                const jobCard = document.createElement('div');
                jobCard.className = `job-card status-${data.status.toLowerCase()}`;
                
                jobCard.innerHTML = `
                    <h3>Job ${jobId}</h3>
                    <p><strong>Status:</strong> ${data.status}</p>
                    <p><strong>Last Update:</strong> ${new Date(data.last_update * 1000).toLocaleString()}</p>
                    ${data.info ? `
                        <p><strong>Name:</strong> ${data.info.name || 'N/A'}</p>
                        <p><strong>Runtime:</strong> ${data.info.elapsed_time || 'N/A'}</p>
                        <p><strong>Node:</strong> ${data.info.node_list || 'N/A'}</p>
                    ` : ''}
                    ${data.error ? `<p style="color: red;"><strong>Error:</strong> ${data.error}</p>` : ''}
                `;
                
                container.appendChild(jobCard);
            }
        }
        
        function updateQueue(queueData) {
            const container = document.getElementById('queue-container');
            
            if (queueData.error) {
                container.innerHTML = `<p style="color: red;">Error: ${queueData.error}</p>`;
                return;
            }
            
            // Group jobs by status
            const statusCounts = {};
            queueData.forEach(job => {
                statusCounts[job.status] = (statusCounts[job.status] || 0) + 1;
            });
            
            let html = '<div>';
            for (const [status, count] of Object.entries(statusCounts)) {
                html += `<span style="margin-right: 20px;"><strong>${status}:</strong> ${count}</span>`;
            }
            html += '</div>';
            
            container.innerHTML = html;
        }
        
        // Auto-refresh every 30 seconds
        setInterval(refreshData, 30000);
        
        // Initial load
        refreshData();
    </script>
</body>
</html>
"""

def main():
    # Create templates directory and file
    import os
    os.makedirs('templates', exist_ok=True)
    with open('templates/dashboard.html', 'w') as f:
        f.write(dashboard_html)
    
    # Start monitoring some jobs (replace with actual job IDs)
    job_ids = [12345, 12346, 12347]
    dashboard.start_monitoring(job_ids)
    
    # Run Flask app
    app.run(host='0.0.0.0', port=5000, debug=True)

if __name__ == "__main__":
    main()
```

## Next Steps

- Learn about [SLURM Jobs](slurm-jobs.md) submission patterns
- Explore [Configuration](../user-guide/configuration.md) for monitoring settings
- Check [Local Jobs](local-jobs.md) for local monitoring examples
- Review [API Reference](../api/submitters.md) for monitoring methods
