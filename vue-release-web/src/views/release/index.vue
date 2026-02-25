<template>
  <div class="app-container">
    <el-card class="operate-container" shadow="never">
      <div style="margin-bottom: 2%">
        <el-alert
          title="配置发布计划，如有配置，先发配置后发版本，暂只支持rancher环境。"
          type="info"
        />
      </div>
      <div class="block">
        <el-row type="flex" class="row-bg" justify="end">
          <el-col :span="3">
            <el-select
              v-model="optionValue.project"
              placeholder="项目"
              style="width:100%"
              clearable
              filterable
              @change="filterSelectTrigger()"
            >
              <el-option
                v-for="item in projectFilterOptions"
                :key="item"
                :label="item"
                :value="item"
              />
            </el-select>
          </el-col>
          <el-col :span="3">
            <el-select
              v-model="optionValue.status"
              style="width:100%"
              placeholder="状态"
              clearable
              filterable
              @change="filterSelectTrigger()"
            >
              <el-option
                v-for="item in statusOptions"
                :key="item"
                :label="item"
                :value="item"
              />
            </el-select>
          </el-col>
          <el-col :span="3">
            <el-select
              v-model="optionValue.owner"
              style="width:100%"
              placeholder="创建人"
              clearable
              filterable
              @change="filterSelectTrigger()"
            >
              <el-option
                v-for="item in ownerOptions"
                :key="item"
                :label="item"
                :value="item"
              />
            </el-select>
          </el-col>
          <el-col :span="6">
            <div class="grid-content bg-purple">
              <el-input v-model="search" style="width: 250px" placeholder="搜索"/>
            </div>
          </el-col>
          <el-col :span="7">
            <div class="grid-content bg-purple-light"/>
          </el-col>
          <el-col :span="2">
            <div class="grid-content bg-purple">
              <el-button type="primary" icon="el-icon-edit" @click="handleCreate()">创建</el-button>
            </div>
          </el-col>
        </el-row>
      </div>
    </el-card>
    <el-table
      :data="list.slice((currentPage-1)*pageSize,currentPage*pageSize)"
      style="width: 100%"
      :header-cell-style="{background:'#eef1f6',color:'#606266'}"
    >
      <el-table-column label="发布名称" sortable>
        <template slot-scope="{row}">
          <span class="link-type" @click="openDetail(row)">{{ row.name }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="project" label="项目"/>
      <el-table-column label="创建时间" sortable>
        <template slot-scope="{row}">
          {{ row.created_time | formatDate }}
        </template>
      </el-table-column>
      <el-table-column label="计划发布时间" sortable>
        <template slot-scope="{row}">
          {{ row.plan_release_time | formatDate }}
        </template>
      </el-table-column>
      <el-table-column label="实际发布时间" sortable>
        <template slot-scope="{row}">
          {{ row.release_time | formatDate }}
        </template>
      </el-table-column>
      <el-table-column label="发布时长" sortable>
        <template slot-scope="{row}">
          <span v-if="row.release_time">{{ row.release_time | duration(row.last_updated_time) }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="owner" label="创建人" sortable/>
      <el-table-column label="状态">
        <template slot-scope="{row}">
          <el-tag v-if="row.status==='发布成功'" type="success">{{ row.status }}</el-tag>
          <el-tag v-else-if="row.status==='发布失败'" type="danger">{{ row.status }}</el-tag>
          <el-tag v-else>{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="发布模块" label="发布模块">
        <template slot-scope="{row}">
          <span class="link-type" @click="showJiraVersion(row.release_contents)">版本详情</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="250px">
        <template slot-scope="scope">
          <el-button
            type="success"
            size="mini"
            @click="openDetail(scope.row)"
          >发布入口
          </el-button>
          <el-button
            :disabled="scope.row.owner!==name || scope.row.status==='发布成功'"
            type="primary"
            size="mini"
            @click="handleEdit(scope.row)"
          >编辑
          </el-button>
          <el-button
            :disabled="scope.row.owner!==name || scope.row.status!=='未发布'"
            type="danger"
            size="mini"
            @click="handleDelete(scope.row)"
          >删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>
    <div class="pagination-container">
      <el-pagination
        align="center"
        :current-page="currentPage"
        :page-sizes="[10,15,20]"
        :page-size="pageSize"
        layout="total, sizes, prev, pager, next, jumper"
        :total="total"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </div>
    <el-dialog title="编辑发布计划" :visible.sync="dialogFormVisible" width="32%">
      <el-form ref="form" :model="form" :rules="rules" label-width="110px">
        <el-form-item label="项目" prop="project" required>
          <el-select v-model="form.project" clearable filterable class="form-width">
            <el-option
              v-for="item in projectOptions"
              :key="item"
              :label="item"
              :value="item"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="发布名称" prop="name" required>
          <el-input v-model="form.name" class="form-width"/>
        </el-form-item>
        <el-form-item label="计划发布时间" prop="plan_release_time" required>
          <el-date-picker
            class="form-width"
            v-model="form.plan_release_time"
            type="datetime"
            placeholder="选择计划发布时间">
          </el-date-picker>
        </el-form-item>
        <el-form-item label="Jira单号" prop="name">
          <el-select
            v-model="form.issueKey"
            filterable
            clearable
            placeholder="请选择发布申请类型工单"
            class="form-width"
            @change="selectTrigger(form.issueKey)"
          >
            <el-option
              v-for="item in issueKeyOptions"
              :key="item"
              :label="item"
              :value="item"
            />
          </el-select>
          <el-table-draggable>
            <el-table
              :data="form.selectList"
              style="width: 100%"
              row-key="index"
            >
              <el-table-column
                type="index"
                label="发布顺序"
                width="100%"
              />
              <el-table-column label="工单">
                <template slot-scope="{row}">
                  <el-link :href="'https://jira.datayes.com/browse/'+row.issue_key" type="success" target="_blank">
                    {{ row.issue_key }}
                  </el-link>
                </template>
              </el-table-column>
              <el-table-column prop="release_version" label="发布版本"/>
              <el-table-column prop="config_file" label="配置文件">
                <template slot-scope="{row}">
                  <span v-if="row.config_file==='无' || !row.config_file ">无</span>
                  <el-popover
                    v-else
                    placement="top-start"
                    width="300"
                    trigger="hover">
                    <div v-for="config in row.config_file.split('\r')" class="text item">
                      {{ config }}
                    </div>
                    <span slot="reference" style="color: #337ab7">有</span>
                  </el-popover>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="50px">
                <template slot-scope="scope">
                  <el-button
                    type="primary"
                    size="mini"
                    icon="el-icon-delete"
                    circle
                    @click="deleteIssueKey(scope.$index,scope.row)"
                  />
                </template>
              </el-table-column>
            </el-table>
          </el-table-draggable>
        </el-form-item>
      </el-form>
      <div slot="footer" class="dialog-footer">
        <el-button @click="dialogFormVisible = false">取 消</el-button>
        <el-button v-if="dialogUpdateEnable" type="primary" @click="updateForm()">确 定</el-button>
        <el-button v-else type="primary" @click="submitForm()">确 定</el-button>
      </div>
    </el-dialog>
    <el-dialog title="jira发布版本" :visible.sync="jiraVersionDialogFormVisible" width="35%">
      <el-table
        :data="jiraVersionList"
        style="width: 100%"
      >
        <el-table-column prop="index" label="发布顺序" width="80px"/>
        <el-table-column label="jira工单">
          <template slot-scope="{row}">
            <el-link :href="'https://jira.datayes.com/browse/'+row.issue_key" type="success" target="_blank">
              {{ row.issue_key }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column prop="release_version" label="发布版本"/>
        <el-table-column prop="rancher_app_version" label="rancher app 版本"/>
        <el-table-column prop="config_file" label="配置文件">
          <template slot-scope="{row}">
            <el-popover
              v-if="row.config_file"
              placement="top-start"
              width="300"
              trigger="hover">
              <div v-for="config in row.config_file.split('\n')" class="text item">
                {{ config }}
              </div>
              <span slot="reference" style="color: #337ab7">有</span>
            </el-popover>
            <span v-else>无</span>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script>

import {getReleaseIssueKey, getReleaseIssueVersion} from '@/api/issue'
import {
  createReleasePlan,
  deleteReleasePlan,
  getReleasePlanProject,
  getReleasePlans,
  updateReleasePlan
} from '@/api/releasePlan'
import ElTableDraggable from 'el-table-draggable'
import {mapGetters} from 'vuex'

const moment = require('moment')
export default {
  name: 'Index',
  filters: {
    duration(startTime, endTime) {
      const moment = require('moment')
      const now = moment(endTime)
      const start = moment(startTime)
      return now.diff(start, 'hours') + 'h' + now.diff(start, 'minutes') % 60 + 'm' + now.diff(start, 'seconds') % 60 + 's'
    }
  },
  components: {
    ElTableDraggable
  },
  data() {
    const validateTime = (rule, value, callback) => {
      // /../ 以/开头,以/结尾 中间的内容为正则表达式
      if (/^([1-9][0-9]|[1-9]).*[hHdDmM]$/.test(value) === false) {
        callback(new Error('Please enter the correct value'))
      } else {
        callback()
      }
    }
    return {
      optionValue: {},
      projectFilterOptions: new Set(),
      statusOptions: new Set(),
      ownerOptions: new Set(),
      list: [],
      fullList: null,
      total: null,
      listLoading: true,
      currentPage: 1,
      pageSize: 10,
      listQuery: {
        pageNum: 1,
        pageSize: 5
      },
      form: {
        selectList: [],
        name: null,
        project: null,
        plan_release_time: null,
        config_file: null,
        issueKey: null,
      },
      projectOptions: [],
      parentId: 0,
      value1: null,
      num: 5,
      search: null,
      dialogFormVisible: false,
      dialogUpdateEnable: false,
      issueKeyOptions: [],
      jiraVersionDialogFormVisible: false,
      jiraVersionList: []
    }
  },
  computed: {
    ...mapGetters([
      'name'
    ])
  },
  watch: {
    search: function (val) {
      if (val) {
        val = val.trim()
        let tempList = this.fullList
        if (this.optionValue.status) {
          tempList = tempList.filter(item => item.status === this.optionValue.status)
        }
        if (this.optionValue.owner) {
          tempList = tempList.filter(item => item.owner === this.optionValue.owner)
        }
        if (this.optionValue.project) {
          tempList = tempList.filter(item => item.project === this.optionValue.project)
        }
        this.list = tempList.filter(function (dataNews) {
          return Object.keys(dataNews).some(function (key) {
            if (String(dataNews[key]).toUpperCase().indexOf(val) > -1) {
              return String(dataNews[key]).toUpperCase().indexOf(val) > -1
            } else {
              return String(dataNews[key]).toLowerCase().indexOf(val) > -1
            }
          })
        })
      } else {
        this.filterSelectTrigger()
      }
      this.total = this.list.length
    }
  },
  created() {
    this.getList()
  },
  methods: {

    dateFormat: function (row, column) {
      const date = row[column.property]
      return moment(date).format('YYYY-MM-DD HH:mm:ss')
    },
    getList() {
      this.listLoading = true
      getReleasePlans().then(response => {
        this.listLoading = false
        this.list = []
        this.fullList = response.data
        this.fullList.forEach(item => {
          this.statusOptions.add(item.status)
          this.ownerOptions.add(item.owner)
          this.projectFilterOptions.add(item.project)
          if (item.project !== 'MDL') {
            this.list.push(item)
          }
        })
        this.total = this.list.length
      })
    },
    filterSelectTrigger() {
      let tempList = this.fullList
      if (this.optionValue.status) {
        tempList = tempList.filter(item => item.status === this.optionValue.status)
      }
      if (this.optionValue.owner) {
        tempList = tempList.filter(item => item.owner === this.optionValue.owner)
      }
      if (this.optionValue.project) {
        tempList = tempList.filter(item => item.project === this.optionValue.project)
      }
      this.list = tempList
      this.total = this.list.length
    },
    selectTrigger(val) {
      const tempList = []
      this.form.selectList.forEach(item => {
        tempList.push(item.issue_key)
      })
      if (val && !tempList.includes(val)) {
        getReleaseIssueVersion({issue_key: val}).then(response => {
          const temp = {}
          temp.issue_key = val
          temp.release_version = response.data.release_version
          temp.rancher_app_version = response.data.rancher_app_version
          temp.config_file = response.data.config_file
          this.form.selectList.push(temp)
        })
      }
    },
    handle(url) {
      window.open(url, '_blank')
    },
    handleSizeChange(val) {
      this.currentPage = 1
      this.pageSize = val
    },
    handleCurrentChange(val) {
      this.currentPage = val
    },
    handleCreate() {
      this.dialogUpdateEnable = false
      this.form.selectList = []
      this.form.name = null
      this.form.issueKey = null
      this.form.project = null
      this.form.plan_release_time = null
      getReleaseIssueKey().then(response => {
        this.issueKeyOptions = response.data
      })
      getReleasePlanProject().then(response => {
        this.projectOptions = response.data
      })
      this.dialogFormVisible = true
      this.$nextTick(() => {
        this.$refs['form'].clearValidate()
      })
    },
    showJiraVersion(val) {
      this.jiraVersionDialogFormVisible = true
      this.jiraVersionList = val
    },
    openDetail(row) {
      this.$router.push({path: '/releaseDetail', query: {name: row.name}})
    },
    submitForm() {
      this.$refs['form'].validate((valid) => {
        if (valid) {
          this.form.plan_release_time = moment(this.form.plan_release_time).format('YYYY-MM-DD HH:mm:ss')
          createReleasePlan(this.form).then(response => {
            this.dialogFormVisible = false
            this.$message({
              message: '创建成功',
              type: 'success',
              duration: 3 * 1000
            })
            this.getList()
          })
        }
      })
    },
    handleDelete(row) {
      this.$confirm('确定删除？', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }).then(() => {
        deleteReleasePlan(row).then(response => {
          this.$message({
            message: '删除成功',
            type: 'success',
            duration: 3 * 1000
          })
          this.getList()
        })
      })
    },
    deleteIssueKey(index, row) {
      this.form.selectList.splice(this.form.selectList.findIndex(item => item.issue_key === row.issue_key), 1)
    },
    handleEdit(row) {
      this.form = Object.assign({}, row)
      this.dialogUpdateEnable = true
      this.form.selectList = row.release_contents
      getReleaseIssueKey().then(response => {
        this.issueKeyOptions = response.data
      })
      getReleasePlanProject().then(response => {
        this.projectOptions = response.data
      })
      this.dialogFormVisible = true
    },
    updateForm() {
      this.$refs['form'].validate((valid) => {
        if (valid) {
          this.form.plan_release_time = moment(this.form.plan_release_time).format('YYYY-MM-DD HH:mm:ss')
          updateReleasePlan(this.form).then(response => {
            this.dialogFormVisible = false
            this.$message({
              message: '更新成功',
              type: 'success',
              duration: 3 * 1000
            })
            this.getList()
          })
        }
      })
    }
  }
}
</script>

<style scoped>
.link-type,
.link-type:focus {
  color: #337ab7;
  cursor: pointer;

&
:hover {
  color: rgb(32, 160, 255);
}

}

.form-width {
  width: 100%;
}
</style>
