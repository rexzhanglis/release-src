<template>
  <div class="app-container">
    <el-card class="operate-container" shadow="never">
      <div class="block">
        <el-row type="flex" class="row-bg" justify="end">
          <el-col :span="3">
            <el-select
              v-model="listQuery.optionValue.status"
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
              v-model="listQuery.optionValue.owner"
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
              <el-input v-model="listQuery.search" style="width: 250px" placeholder="搜索" @change="search()"/>
            </div>
          </el-col>
          <el-col :span="10">
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
      :data="list"
      style="width: 100%"
      :header-cell-style="{background:'#eef1f6',color:'#606266'}"
    >
      <el-table-column label="发布名称" sortable>
        <template slot-scope="{row}">
          <span class="link-type" @click="openDetail(row)">{{ row.name }}</span>
        </template>
      </el-table-column>
      <el-table-column label="类型" sortable>
        <template slot-scope="{row}">
          <span v-if="row.type==='config'">配置变更</span>
          <span v-if="row.type==='version'">版本发布</span>
        </template>
      </el-table-column>
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
      <el-table-column label="发布对象">
        <template slot-scope="{row}">
          <span class="link-type" @click="showReleaseObject(row.release_contents)">详情</span>
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
    <el-dialog title="编辑发布计划" :visible.sync="dialogFormVisible" width="60%" :close-on-click-modal="false">
      <el-form ref="form" :model="form" :rules="rules" label-width="110px">
        <el-form-item label="发布名称" prop="name" required>
          <el-input v-model="form.name" class="form-width"/>
        </el-form-item>
        <el-form-item label="计划发布时间" prop="plan_release_time" required>
          <el-date-picker
            v-model="form.plan_release_time"
            class="form-width"
            type="datetime"
            placeholder="选择计划发布时间"
          />
        </el-form-item>
        <el-form-item label="类型" required>
          <el-radio-group v-model="form.type" @change="radioChange()">
            <el-radio label="version">版本发布</el-radio>
            <el-radio label="config">仅配置更新</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.type==='version'" label="Jira单号" required>
          <el-select
            v-model="form.issue_key"
            filterable
            clearable
            placeholder="请选择发布申请类型工单"
            class="form-width"
            @change="jiraSelectTrigger(form.issue_key)"
          >
            <el-option
              v-for="item in issueKeyOptions"
              :key="item"
              :label="item"
              :value="item"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="发布对象" prop="release_object">
          <el-select
            v-model="form.release_object"
            filterable
            clearable
            placeholder="服务器+IP+服务名"
            class="form-width"
            @change="selectTrigger(form.release_object)"
          >
            <el-option
              v-for="item in releaseObjectOptions"
              :key="item"
              :label="item"
              :value="item"
            />
          </el-select>
          <el-link :href="mdlLabelUrl" target="_blank">
            <el-button style="margin-left: 10px" icon="el-icon-edit" circle></el-button>
          </el-link>
          <el-table-draggable>
            <el-table
              :data="form.selectList"
              style="width: 100%"
              row-key="index"
            >
              <el-table-column
                type="index"
                label="发布顺序"
                width="80px"
              />
              <el-table-column v-if="form.type==='version'" prop="release_version" label="发布版本"/>
              <el-table-column prop="release_object" label="发布对象"/>
              <el-table-column label="操作" width="120px">>
                <template slot-scope="{row}">
                  <el-button
                    type="warning"
                    size="mini"
                    icon="el-icon-delete"
                    circle
                    @click="deleteServer(row)"
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
    <el-dialog title="mdl发布对象" :visible.sync="releaseObjectDialogFormVisible" width="35%">
      <el-table
        :data="releaseObjectList"
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
        <el-table-column prop="release_object" label="发布对象"/>
        <el-table-column prop="release_version" label="发布版本"/>
      </el-table>
    </el-dialog>
  </div>
</template>

<script>

import {getMdlReleaseIssueKey, getMdlReleaseIssueVersion} from '@/api/issue'
import {
  createReleasePlan,
  deleteReleasePlan, getReleasePlanOptions,
  getReleasePlans,
  updateReleasePlan
} from '@/api/releasePlan'
import ElTableDraggable from 'el-table-draggable'
import {mapGetters} from 'vuex'
import { getMdlReleaseServer} from '@/api/server'

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
      statusOptions: new Set(),
      ownerOptions: new Set(),
      list: [],
      total: null,
      listLoading: true,
      currentPage: 1,
      pageSize: 10,
      listQuery: {
        page: 1,
        type: 'MDL',
        search: null,
        optionValue: {
          status: '',
          owner: ''
        }
      },
      form: {
        selectList: [],
        name: '',
        project: 'MDL',
        type: 'version',
        plan_release_time: '',
        issue_key: '',
        release_object: ''
      },
      releaseObjectOptions: [],
      projectOptions: [],
      parentId: 0,
      value1: null,
      num: 5,
      dialogFormVisible: false,
      dialogUpdateEnable: false,
      issueKeyOptions: [],
      releaseObjectDialogFormVisible: false,
      releaseObjectList: [],
      releaseObjectType: '',
      dialogServerFormVisible: false,
      labelToServer: {},
      mdlLabelUrl: window.config.MDL_LABEL_URL
    }
  },
  computed: {
    ...mapGetters([
      'name'
    ])
  },
  created() {
    this.getList()
    this.getReleasePlanOptions()
  },
  methods: {
    dateFormat: function (row, column) {
      const date = row[column.property]
      return moment(date).format('YYYY-MM-DD HH:mm:ss')
    },
    getList() {
      this.listLoading = true
      getReleasePlans(this.listQuery).then(response => {
        this.listLoading = false
        const temp = response.data.results
        this.total = response.data.count
        this.list = []
        temp.forEach(item => {
          item.type = item.release_contents[0].type
          this.list.push(item)
        })
      })
    },
    getReleasePlanOptions() {
      getReleasePlanOptions({type: 'MDL'}).then(response => {
        const data = response.data
        this.statusOptions = data.status
        this.ownerOptions = data.owner
      })
    },
    filterSelectTrigger() {
      this.listQuery.page = 1
      this.getList()
    },
    search() {
      if (this.listQuery.search) {
        this.listQuery.search = this.listQuery.search.trim()
      }
      this.getList()
    },
    selectTrigger(val) {
      const tempList = []
      this.form.selectList.forEach(item => {
        tempList.push(item.release_object)
      })
      if (val && !tempList.includes(val)) {
        let select_release_object_list = []
        if (val.startsWith("label_")) {
          select_release_object_list = this.labelToServer[val]
        } else {
          select_release_object_list.push(val)
        }
        if (this.form.type === 'version') {
          getMdlReleaseIssueVersion({issue_key: this.form.issue_key}).then(response => {
            select_release_object_list.forEach(item => {
              const temp = {}
              temp.release_version = response.data
              temp.release_object = item
              temp.config_file = ''
              this.form.selectList.push(temp)
            })
          })
        } else if (this.form.type === 'config') {
          select_release_object_list.forEach(item => {
            const temp = {}
            temp.release_object = item
            temp.config_file = ''
            this.form.selectList.push(temp)
          })
        }
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
      this.listQuery.page = val
      this.getList()
    },
    handleCreate() {
      this.dialogUpdateEnable = false
      this.form.selectList = []
      this.form.name = ''
      this.form.issue_key = ''
      this.form.plan_release_time = ''
      this.form.release_object = ''
      this.form.type = 'version'
      getMdlReleaseIssueKey().then(response => {
        this.issueKeyOptions = response.data
      })
      getMdlReleaseServer().then(response => {
        this.releaseObjectOptions = response.data.release_object
        this.labelToServer = response.data.label_to_server
      })
      this.dialogFormVisible = true
      this.$nextTick(() => {
        this.$refs['form'].clearValidate()
      })
    },
    openDetail(row) {
      this.$router.push({path: '/releaseDetail', query: {name: row.name}})
    },
    isSelectTableListValid() {
      // 是否选择了发布对象
      if (this.form.selectList.length === 0) {
        this.$message({
          message: '请选择至少一个发布对象',
          type: 'error',
          duration: 3 * 1000
        })
        return false
      }
      return true
    },
    submitForm() {
      this.$refs['form'].validate((valid) => {
        if (valid) {
          if (this.isSelectTableListValid()) {
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
    deleteServer(row) {
      this.form.selectList.splice(this.form.selectList.findIndex(item => item.release_object === row.release_object), 1)
    },
    handleEdit(row) {
      this.form = Object.assign({}, row)
      this.dialogUpdateEnable = true
      this.form.type = row.release_contents[0].type
      this.form.issue_key = row.release_contents[0].issue_key
      this.form.selectList = row.release_contents.map(v => {
        this.$set(v, 'edit', false)
        return v
      })
      getMdlReleaseIssueKey().then(response => {
        this.issueKeyOptions = response.data
      })
      getMdlReleaseServer().then(response => {
        this.releaseObjectOptions = response.data.release_object
        this.labelToServer = response.data.label_to_server
      })
      this.dialogFormVisible = true
    },
    handleReleaseServerCreate() {
      this.dialogServerFormVisible = true
    },
    updateForm() {
      this.$refs['form'].validate((valid) => {
        if (valid) {
          if (this.isSelectTableListValid()) {
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
        }
      })
    },
    jiraSelectTrigger() {
      this.$forceUpdate()
    },
    radioChange() {
      this.$forceUpdate()
    },
    showReleaseObject(val) {
      this.releaseObjectDialogFormVisible = true
      this.releaseObjectList = val
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
  width: 35%;
}
</style>
