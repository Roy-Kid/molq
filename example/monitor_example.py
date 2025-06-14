"""Monitor a long running local job."""

from molq import submit

local = submit('local', 'local')

@local
def long_job() -> int:
    job_id = yield {
        'cmd': ['sleep', '5'],
        'job_name': 'long',
    }
    return job_id

if __name__ == '__main__':
    jid = long_job()
    # start monitoring until completion
    submit.get_cluster('local').monitor_all(interval=1)
    print('Finished job', jid)
