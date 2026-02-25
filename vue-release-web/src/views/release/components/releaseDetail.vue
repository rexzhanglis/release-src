<template>
  <div class="app-container">
    <el-card>
      <el-descriptions title="任务信息" style="font-size: large">
        <el-descriptions-item label="名称">{{ taskDetail.name }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ taskDetail.created_time | formatDate }}</el-descriptions-item>
        <el-descriptions-item label="计划发布时间">{{ taskDetail.plan_release_time | formatDate }}</el-descriptions-item>
        <el-descriptions-item label="创建用户">{{ taskDetail.owner }}</el-descriptions-item>
      </el-descriptions>
      <el-descriptions title="执行信息" style="font-size: large;margin-top: 1%">
        <el-descriptions-item label="执行用户">{{ releaseDetail.user }}</el-descriptions-item>
        <el-descriptions-item label="开始时间"><span
          v-if="releaseDetail.created_time"
        >{{ releaseDetail.created_time | formatDate }}</span></el-descriptions-item>
        <el-descriptions-item label="任务耗时"><span
          v-if="releaseDetail.created_time"
        >{{ releaseDetail.created_time | duration(releaseDetail.last_updated_time) }}</span></el-descriptions-item>
        <el-descriptions-item label="任务状态">
          <span v-if="releaseDetail.status==='发布失败'" style="color: orangered">{{ releaseDetail.status }}</span>
          <span v-else style="color: #67C23A">{{ releaseDetail.status }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="流程提示">{{ releaseDetail.prompt }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card>
      <el-collapse v-model="activeNames" class="el-collapse-item__Bos">
        <el-collapse-item name="1">
          <span slot="title" class="collapse-title">流程图</span>
          <el-row v-if="editVisible()" style="margin-top: 1%">
            <el-col :span="12">
              <el-button v-if="release_button==='发布'" :disabled="!isRelease" type="success" @click="deploy()">发布
              </el-button>
              <el-button v-if="release_button==='暂停'" :disabled="!isRelease" type="warning" @click="suspend()">暂停
              </el-button>
              <el-button v-if="release_button==='再发布'" :disabled="!isRelease" type="success" @click="reDeploy()">再发布
              </el-button>
              <el-button :disabled="!isRollback" type="info" @click="rollback()">回滚</el-button>
              <el-button :disabled="!isFail" type="warning" @click="failSkip()">失败跳过</el-button>
              <el-button :disabled="!isFail" type="primary" @click="failRetry()">失败重试</el-button>
            </el-col>
          </el-row>
          <el-steps
            v-if="this.taskDetail.project === 'MDL'"
            :space="250"
            align-center
            style="margin-top: 1.5%"
            :active="releaseDetail.active-1"
            :process-status="processStatus"
          >
            <el-step
              v-for="item in moduleList"
              :title="item.release_object"
              :description="item.release_version"
              :status="item.status"
            />
          </el-steps>
          <el-steps
            v-else
            :space="250"
            style="margin-top: 1.5%"
            align-center
            :active="releaseDetail.active-1"
            :process-status="processStatus"
          >
            <el-step
              v-for="item in moduleList"
              :title="item.release_version"
              :status="item.status"
            />
          </el-steps>
        </el-collapse-item>
        <el-collapse-item name="2">
          <span slot="title" class="collapse-title">日志</span>
          <div v-for="item in log">{{ item }}</div>
        </el-collapse-item>
      </el-collapse>

    </el-card>
  </div>
</template>

<script>

import {deploy, failRetry, failSkip, getReleaseDetailInfo, reDeploy, rollback, suspend} from '@/api/releaseDetail'
import {getReleasePlanInfo} from '@/api/releasePlan'
import {Message} from 'element-ui'
import {mapGetters} from 'vuex'
import {isVisible} from '@/utils/auth'

export default {
  name: 'ReleaseDetail',
  filters: {
    duration(startTime, endTime) {
      const moment = require('moment')
      const now = moment(endTime)
      const start = moment(startTime)
      return now.diff(start, 'hours') + 'h' + now.diff(start, 'minutes') % 60 + 'm' + now.diff(start, 'seconds') % 60 + 's'
    }
  },
  computed: {
    ...mapGetters([
      'name'
    ])
  },
  data() {
    return {
      moduleList: [],
      list: null,
      fullList: null,
      total: null,
      listLoading: true,
      releasePlanName: null, // 发布名称
      taskDetail: null,
      isFail: false, // 任务失败的修改为fail
      isRollback: false, // 任务失败的修改为fail
      isRelease: true,

      releaseDetail: {
        user: null,
        created_time: null,
        last_updated_time: null,
        status: null,
        prompt: null
      },
      log: [],
      // 发布按钮值有三种类型  发布  暂停 再发布
      release_button: '发布',
      // step
      processStatus: 'process',
      activeNames: ['1']
    }
  },
  created() {
    this.releasePlanName = this.$route.query.name
    this.getReleasePlanInfo()
  },

  beforeDestroy() {
    clearInterval(this.timer)
  },
  methods: {
    handle(url) {
      window.open(url, '_blank')
    },
    editVisible() {
      // 当发布成功且大于一周后 所有按钮不可见 即也不能进行回滚操作
      if (this.releaseDetail.status === '发布成功' && this.isMoreThanWeek()) {
        return false
      }
      if (isVisible('devops')) {
        return true
      }
      if (isVisible('admin')) {
        return true
      }
      return false
    },
    //  是否大于一周
    isMoreThanWeek() {
      const releaseSuccessTimestamp = (new Date(this.releaseDetail.last_updated_time)).getTime() + 7 * 24 * 60 * 60 * 1000
      // 发布成功大于一周
      if (releaseSuccessTimestamp < new Date()) {
        return true
      }
      return false
    },
    getReleasePlanInfo() {
      getReleasePlanInfo({name: this.releasePlanName}).then(response => {
        this.taskDetail = response.data
        if (this.taskDetail.project === 'MDL') {
          this.taskDetail.release_contents.forEach(item => {
            this.moduleList.push({
              'release_version': item.release_version,
              'status': item.status,
              'release_object': item.release_object
            })
          })
        } else {
          this.taskDetail.release_contents.forEach(item => {
            this.moduleList.push({'release_version': item.release_version, 'status': item.status})
          })
        }
        this.getReleaseDetailInfo()
      })
    },
    getReleaseDetailInfo() {
      getReleaseDetailInfo({name: this.releasePlanName}).then(response => {
          if (response.data) {
            this.releaseDetail = response.data
            this.isRollback = true
            this.log = this.releaseDetail.log.split('\n')
            // 处理流程图中的模块
            const temp = []
            this.releaseDetail.step_status.forEach(item => {
              temp.push({
                'release_version': item.release_version,
                'status': item.status,
                'release_object': item.release_object
              })
            })
            this.moduleList = temp
            // 判断升级状态
            if (this.releaseDetail.status === '发布中') {
              this.release_button = '暂停'
              this.isFail = false
              if (!this.timer) {
                this.startTimer()
              }
            } else if (this.releaseDetail.status === '暂停') {
              this.release_button = '再发布'
              this.isFail = false
            } else if (this.releaseDetail.status === '发布失败') {
              this.isFail = true
              this.isRelease = false
            } else if (this.releaseDetail.status === '发布成功') {
              this.isRelease = false
              this.isFail = false
              if (this.timer) {
                clearInterval(this.timer)
              }
            } else if (this.releaseDetail.status === '回滚中') {
              this.isRelease = false
              this.isFail = false
              this.isRollback = false
              // 用于用户手动刷新页面
              if (!this.timer) {
                this.startTimer()
              }
            } else if (this.releaseDetail.status === '回滚成功') {
              this.isRelease = true
              this.release_button = '发布'
              this.isFail = false
              this.isRollback = false
              if (this.timer) {
                clearInterval(this.timer)
              }
            } else if (this.releaseDetail.status === '回滚失败') {
              this.isRelease = false
              this.isFail = true
              this.isRollback = false
            }
          }
        }
      )
    },
    sleep(ms) {
      return new Promise(function (resolve) {
        setTimeout(resolve, ms)
      })
    },
    deploy() {
      this.$confirm('确定升级？', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }).then(() => {
        this.release_button = '暂停'
        deploy({name: this.releasePlanName}).then(response => {
          this.handleFail(response)
        })
        this.startTimer()
      })
    },
    suspend() {
      this.$confirm('确定暂停？', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }).then(() => {
        clearInterval(this.timer)
        this.release_button = '再发布'
        suspend({name: this.releasePlanName}).then(response => {
          this.$message({
            message: '暂停成功',
            type: 'success',
            duration: 3 * 1000
          })
        })
        this.suspendTimer()
      })
    },
    reDeploy() {
      this.$confirm('确定再发布？', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }).then(() => {
        this.release_button = '暂停'
        reDeploy({name: this.releasePlanName}).then(response => {
          this.handleFail(response)
        })
        this.startTimer()
      })
    },
    rollback() {
      this.$confirm('确定回滚？', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }).then(() => {
        rollback({name: this.releasePlanName}).then(response => {
          this.handleFail(response)
        })
        this.startTimer()
      })
    },
    failSkip() {
      this.$confirm('确定失败跳过？', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }).then(() => {
        failSkip({name: this.releasePlanName}).then(response => {
          this.handleFail(response)
        })
        this.startTimer()
      })
    },
    failRetry() {
      this.$confirm('确定失败重试？', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }).then(() => {
        failRetry({name: this.releasePlanName}).then(response => {
          this.handleFail(response)
        })
        this.startTimer()
      })
    },
    handleFail(response) {
      clearInterval(this.timer)
      this.getReleaseDetailInfo()
      if (response.data === 'fail') {
        Message({
          message: response.message,
          type: 'error',
          duration: 5 * 1000
        })
      }
    },
    async startTimer() {
      // 创建定时任务 刷新间隔5s
      await this.sleep(500)
      this.getReleaseDetailInfo()
      this.timer = setInterval(this.getReleaseDetailInfo, 5 * 1000)
    },
    async suspendTimer() {
      await this.sleep(5 * 1000)
      this.getReleaseDetailInfo()
    }
  }
}
</script>

<style scoped>
.collapse-title {
  flex: 1 0 90%;
  order: 1;
}

.el-collapse-item__Bos >>> .el-collapse-item__header {
  font-size: 1.2rem !important;
  background: #f2f5f5;

}

.my-label {
  background: #909399
}

.my-content {
  background: #909399
}

</style>
