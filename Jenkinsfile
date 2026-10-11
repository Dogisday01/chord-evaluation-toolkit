pipeline {
    agent { label 'docker' }
    options {
        skipDefaultCheckout(true)
        disableConcurrentBuilds()
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '30', artifactNumToKeepStr: '15'))
    }
    parameters {
        string(name: 'COMMIT_SHA', defaultValue: '', description: 'Optional exact trusted 40-character SHA')
        string(name: 'TRACKED_BRANCH', defaultValue: env.TRUSTED_BRANCH ?: 'main', description: 'Trusted repository branch containing the revision')
    }
    stages {
        stage('Checkout exact revision') {
            steps {
                script {
                    if (params.COMMIT_SHA && !(params.COMMIT_SHA ==~ /[0-9a-fA-F]{40}/)) {
                        error('COMMIT_SHA must be empty or exactly 40 hexadecimal characters')
                    }
                    if (!(params.TRACKED_BRANCH ==~ /[A-Za-z0-9][A-Za-z0-9_.\/-]*/) || params.TRACKED_BRANCH.contains('..')) {
                        error('TRACKED_BRANCH must be a valid trusted branch name')
                    }
                }
                deleteDir()
                checkout scm
                withEnv(["REQUESTED_SHA=${params.COMMIT_SHA}", "BUILD_BRANCH=${params.TRACKED_BRANCH}"]) {
                    sh '''
                        set -eu
                        git check-ref-format "refs/heads/$BUILD_BRANCH"
                        git fetch --no-tags origin "refs/heads/$BUILD_BRANCH"
                        if [ -n "$REQUESTED_SHA" ]; then
                            git cat-file -e "$REQUESTED_SHA^{commit}"
                            git merge-base --is-ancestor "$REQUESTED_SHA" FETCH_HEAD
                            git checkout --detach "$REQUESTED_SHA"
                        else
                            git checkout --detach FETCH_HEAD
                        fi
                        mkdir -p artifacts
                        git rev-parse HEAD > artifacts/commit.txt
                        docker version > artifacts/docker-version.txt
                    '''
                }
                script {
                    env.CHECKED_SHA = readFile('artifacts/commit.txt').trim()
                    env.IMAGE_TAG = "chord-eval:${env.CHECKED_SHA}-${env.BUILD_NUMBER}"
                    env.TEST_TAG = "chord-eval-test:${env.CHECKED_SHA}-${env.BUILD_NUMBER}"
                    env.TEST_CONTAINER = "chord-ci-test-${env.BUILD_NUMBER}"
                    env.SMOKE_CONTAINER = "chord-ci-smoke-${env.BUILD_NUMBER}"
                    currentBuild.description = env.CHECKED_SHA.take(12)
                    echo "Checking commit ${env.CHECKED_SHA}"
                }
            }
        }
        stage('Build test environment') {
            steps {
                sh 'docker build --target test --tag "$TEST_TAG" .'
            }
        }
        stage('Ruff and pytest') {
            steps {
                sh '''
                    set -eu
                    docker create --name "$TEST_CONTAINER" --network none "$TEST_TAG" sh -c '
                        ruff check . > /tmp/ruff.log 2>&1; lint_status=$?
                        python -m pytest --junitxml=/tmp/test-results.xml > /tmp/pytest.log 2>&1; test_status=$?
                        cat /tmp/ruff.log /tmp/pytest.log
                        test "$lint_status" -eq 0 && test "$test_status" -eq 0
                    '
                    docker start --attach "$TEST_CONTAINER"
                '''
            }
            post {
                always {
                    sh '''
                        set -eu
                        docker cp "$TEST_CONTAINER:/tmp/test-results.xml" artifacts/test-results.xml
                        docker cp "$TEST_CONTAINER:/tmp/ruff.log" artifacts/ruff.log
                        docker cp "$TEST_CONTAINER:/tmp/pytest.log" artifacts/pytest.log
                    '''
                    junit testResults: 'artifacts/test-results.xml', allowEmptyResults: false
                }
            }
        }
        stage('Build runtime image') {
            steps {
                sh '''
                    docker build --target runtime --build-arg "VCS_REF=$CHECKED_SHA" --tag "$IMAGE_TAG" .
                    docker image inspect "$IMAGE_TAG" > artifacts/image-inspect.json
                '''
            }
        }
        stage('Runtime known answer and real data') {
            steps {
                sh '''
                    set -eu
                    docker create --name "$SMOKE_CONTAINER" --network none \
                        --env "CODE_REVISION=$CHECKED_SHA" --entrypoint sh \
                        "$IMAGE_TAG" /tmp/worker-checks.sh
                    docker cp examples "$SMOKE_CONTAINER:/tmp/examples"
                    docker cp infra/jenkins/worker-checks.sh "$SMOKE_CONTAINER:/tmp/worker-checks.sh"
                    docker start --attach "$SMOKE_CONTAINER"
                    docker cp "$SMOKE_CONTAINER:/tmp/results/." artifacts/
                '''
            }
        }
    }
    post {
        always {
            script {
                try {
                    archiveArtifacts artifacts: 'artifacts/**', allowEmptyArchive: true, fingerprint: true
                } finally {
                    sh '''
                        cleanup_status=0
                        for name in "${TEST_CONTAINER:-}" "${SMOKE_CONTAINER:-}"; do
                            [ -n "$name" ] || continue
                            if containers=$(docker container ls -aq --filter "name=^/${name}$"); then
                                if [ -n "$containers" ]; then
                                    if ! docker rm --force "$name"; then
                                        echo "Failed to remove build container $name" >&2
                                        cleanup_status=1
                                    fi
                                fi
                            else
                                echo "Failed to inspect build container $name" >&2
                                cleanup_status=1
                            fi
                        done
                        exit "$cleanup_status"
                    '''
                }
            }
        }
    }
}
