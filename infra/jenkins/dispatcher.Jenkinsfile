// Configure this job from the trusted control branch, never the demonstration branch.
// Python state lives on the agent's persistent dispatcher_state volume.
pipeline {
    agent { label 'docker' }
    options {
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '50'))
        timeout(time: 120, unit: 'MINUTES')
        skipDefaultCheckout(true)
    }
    triggers { cron('* * * * *') }
    parameters {
        string(name: 'TRACKED_BRANCH', defaultValue: env.TRUSTED_BRANCH ?: 'main',
               description: 'Remote branch to queue; use a separate demo branch for failures')
    }
    stages {
        stage('Load trusted dispatcher') {
            steps { checkout scm }
        }
        stage('Queue and dispatch commits') {
            steps {
                script {
                    def branch = params.TRACKED_BRANCH
                    if (!(branch ==~ /[A-Za-z0-9][A-Za-z0-9_.\/-]*/)) {
                        error('Invalid tracked branch')
                    }
                    // Percent cannot occur in valid branch names, so encoding is unambiguous.
                    def stateFile = '/var/jenkins-dispatcher/' + branch.replace('/', '%') + '.json'
                    withEnv(["TRACKED_BRANCH=${branch}", "STATE_FILE=${stateFile}"]) {
                        sh '''python3 scripts/jenkins_dispatcher.py --state "$STATE_FILE" \
                            poll --repo . --branch "$TRACKED_BRANCH"'''
                        while (true) {
                            def sha = sh(returnStdout: true, script:
                                'python3 scripts/jenkins_dispatcher.py --state "$STATE_FILE" next'
                            ).trim()
                            if (!sha) { break }
                            if (!(sha ==~ /[0-9a-f]{40}/)) { error('Invalid queued commit SHA') }
                            echo "Dispatching ${branch} commit ${sha}"
                            // A failed worker is still processed. An interrupted dispatcher leaves
                            // its pending SHA intact; restart may repeat that worker (at least once).
                            def run = build(job: 'chord-evaluation-worker', wait: true,
                                propagate: false,
                                parameters: [string(name: 'COMMIT_SHA', value: sha),
                                             string(name: 'TRACKED_BRANCH', value: branch)])
                            def result = run.result
                            if (!(result in ['SUCCESS', 'FAILURE', 'UNSTABLE',
                                             'ABORTED', 'NOT_BUILT'])) {
                                error('Worker returned an unsupported result')
                            }
                            withEnv(["COMMIT_SHA=${sha}", "WORKER_RESULT=${result}"]) {
                                sh '''python3 scripts/jenkins_dispatcher.py --state "$STATE_FILE" \
                                    complete --sha "$COMMIT_SHA" --result "$WORKER_RESULT"'''
                            }
                            echo "Processed ${sha}: ${result} (worker #${run.number})"
                        }
                    }
                }
            }
        }
    }
}
