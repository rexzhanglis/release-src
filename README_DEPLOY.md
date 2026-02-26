# 部署测试指南

## 1. 镜像构建与导出（在开发机/构建机执行）
首先构建镜像：
```bash
docker-compose build
```

然后导出镜像为 tar 包：
```bash
docker save -o release-images.tar release-backend:v1.0.0 release-web:v1.0.0 paramiko/sshd:latest
```

## 2. 传输文件
将以下文件传输到目标机器：
1. `release-images.tar`
2. `docker-compose.deploy.yml`

## 3. 镜像导入与启动（在目标机器执行）
导入镜像：
```bash
docker load -i release-images.tar
```

启动服务（指定部署专用的 compose 文件）：
```bash
docker-compose -f docker-compose.deploy.yml up -d
```

## 4. 初始化数据库
**注意：** 您已配置连接现有数据库，请跳过迁移步骤，除非您确定需要重新初始化表结构。
如果需要迁移：
```bash
docker-compose -f docker-compose.deploy.yml exec release-backend python manage.py migrate
```

## 5. 准备测试数据
登录到后端容器，创建一个测试用户和配置实例：
```bash
docker-compose -f docker-compose.deploy.yml exec release-backend python manage.py shell
```
**注意：** 如果您的现有数据库中已有数据，请酌情跳过创建用户步骤。
在 Python shell 中执行：
```python
from account.models import User
from mdl.models import ServiceType, ConfigInstance, ConfigFile

# 创建用户
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin')

# 创建服务类型
st, _ = ServiceType.objects.get_or_create(name='test-service')

# 创建配置实例（指向 target-host 容器）
# 注意：host_ip 使用 docker-compose 网络中的服务名 'target-host'
ci, _ = ConfigInstance.objects.get_or_create(
    service_type=st,
    name='test-instance',
    defaults={
        'host_ip': 'target-host',
        'port': 8080,
        'install_dir': '/tmp/app',
        'backups_dir': '/tmp/backups',
        'service_name': 'test-service'
    }
)

# 创建配置文件
ConfigFile.objects.get_or_create(
    instance=ci,
    filename='config.json',
    defaults={'content': {'key': 'value'}, 'raw_content': '{"key": "value"}'}
)
```

## 6. 测试 Ansible 部署
1. 访问前端页面：`http://<您的Linux机器IP>:9528`
2. 登录（默认 admin/admin，如果创建了的话，或者使用 CAS 登录）
3. 进入“配置管理” -> “配置文件”
4. 选中 `test-service/test-instance/config.json`
5. 点击“部署”
6. 后端容器会执行 Ansible Playbook，通过 SSH 连接到 `target-host` 容器并部署文件。

## 7. 验证部署结果
检查 `target-host` 容器中是否生成了文件：
```bash
docker-compose -f docker-compose.deploy.yml exec target-host ls -l /tmp/app/config.json
docker-compose -f docker-compose.deploy.yml exec target-host cat /tmp/app/config.json
```
