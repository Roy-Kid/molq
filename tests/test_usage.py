from h_submitor import submit

class TestRegisterCluster:

    def test_register(self):

        # register cluster
        @submit('cluster_alpha', 'slurm')
        def foo(a: int, b: int):
            # workload
            job_id = yield dict()
            return job_id
        
        assert submit.get_n_clusters() == 1

        # reuse without config
        @submit('cluster_alpha')
        def bar(a: int, b: int):
            # workload
            job_id = yield dict()

        assert submit.get_n_clusters() == 1

    def test_get_cluster_external(self):

        cluster_alpha = submit('cluster_alpha')
        # cluster_alpha.block_until_complete()

    