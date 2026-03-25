pipeline {
    agent any

    parameters {
        string(name: 'VERSION', defaultValue: 'v1.0.0', description: '镜像版本号，例如 v1.0.1')
        booleanParam(name: 'BUILD_BACKEND',  defaultValue: true,  description: '构建后端镜像')
        booleanParam(name: 'BUILD_FRONTEND', defaultValue: true,  description: '构建前端镜像')
        booleanParam(name: 'PUSH_IMAGE',     defaultValue: true,  description: '推送到镜像仓库')
    }

    environment {
        REGISTRY       = 'registry.datayes.com'
        BACKEND_IMAGE  = "${REGISTRY}/automation/release-backend"
        FRONTEND_IMAGE = "${REGISTRY}/automation/release-web"
        // Jenkins 中配置 ID 为 registry-datayes 的 Username/Password 凭据
        DOCKER_CRED    = 'registry-datayes'
        // 隔离 docker config，避免以 root 写入 /home/jenkins/.docker/config.json
        DOCKER_CONFIG  = "${WORKSPACE}/.docker"
    }

    stages {
        stage('Checkout') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'jenkins_git',
                    usernameVariable: 'GIT_USER',
                    passwordVariable: 'GIT_TOKEN'
                )]) {
                    sh '''
                        if [ -d .git ]; then
                            git fetch http://${GIT_USER}:${GIT_TOKEN}@git.datayes.com/yinyin.zhang/release-src.git
                            git reset --hard FETCH_HEAD
                        else
                            git clone http://${GIT_USER}:${GIT_TOKEN}@git.datayes.com/yinyin.zhang/release-src.git .
                        fi
                    '''
                }
            }
        }

        stage('Build Backend') {
            when { expression { params.BUILD_BACKEND } }
            steps {
                dir('release') {
                    sh """
                        docker build \\
                            -f docker/Dockerfile \\
                            -t ${BACKEND_IMAGE}:${params.VERSION} \\
                            -t ${BACKEND_IMAGE}:latest \\
                            .
                    """
                }
            }
        }

        stage('Build Frontend') {
            when { expression { params.BUILD_FRONTEND } }
            steps {
                dir('vue-release-web') {
                    sh """
                        docker build \\
                            -f docker/Dockerfile \\
                            -t ${FRONTEND_IMAGE}:${params.VERSION} \\
                            -t ${FRONTEND_IMAGE}:latest \\
                            .
                    """
                }
            }
        }

        stage('Push Images') {
            when { expression { params.PUSH_IMAGE } }
            steps {
                withCredentials([usernamePassword(
                    credentialsId: "${DOCKER_CRED}",
                    usernameVariable: 'DOCKER_USER',
                    passwordVariable: 'DOCKER_PASS'
                )]) {
                    sh '''
                        mkdir -p "${DOCKER_CONFIG}"
                        AUTH=$(printf '%s:%s' "$DOCKER_USER" "$DOCKER_PASS" | base64 | tr -d '\n')
                        printf '{"auths":{"%s":{"auth":"%s"}}}' "$REGISTRY" "$AUTH" > "${DOCKER_CONFIG}/config.json"
                        chmod 600 "${DOCKER_CONFIG}/config.json"
                    '''

                    script {
                        if (params.BUILD_BACKEND) {
                            sh "docker push ${BACKEND_IMAGE}:${params.VERSION}"
                            sh "docker push ${BACKEND_IMAGE}:latest"
                        }
                        if (params.BUILD_FRONTEND) {
                            sh "docker push ${FRONTEND_IMAGE}:${params.VERSION}"
                            sh "docker push ${FRONTEND_IMAGE}:latest"
                        }
                    }

                    sh 'rm -rf "${DOCKER_CONFIG}"'
                }
            }
        }
    }

    post {
        success {
            echo "镜像构建推送成功: ${params.VERSION}"
        }
        failure {
            echo "构建失败，请检查日志"
        }
        always {
            // 清理 docker 凭据（防止 push 阶段失败后残留）
            sh 'rm -rf "${DOCKER_CONFIG}" || true'
            // 清理本地镜像节省磁盘
            sh """
                docker rmi ${BACKEND_IMAGE}:${params.VERSION}  || true
                docker rmi ${BACKEND_IMAGE}:latest             || true
                docker rmi ${FRONTEND_IMAGE}:${params.VERSION} || true
                docker rmi ${FRONTEND_IMAGE}:latest            || true
            """
        }
    }
}
