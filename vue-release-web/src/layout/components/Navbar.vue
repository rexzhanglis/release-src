<template>
  <div class="navbar">
    <hamburger :is-active="sidebar.opened" class="hamburger-container" @toggleClick="toggleSideBar" />
    <breadcrumb class="breadcrumb-container" />
    <div style="margin:15px auto;">
      <el-dropdown style="float:right;display: flex;" trigger="click">
        <i>{{ name }}</i>
        <el-dropdown-menu slot="dropdown" class="user-dropdown">
          <el-dropdown-item divided @click.native="logout">
            <span style="display:block;">Log Out</span>
          </el-dropdown-item>
        </el-dropdown-menu>
      </el-dropdown>
      <el-dropdown style="float:right;display: flex;margin-right: 20px;" trigger="click">
        <i class="el-icon-question" />
        <el-dropdown-menu slot="dropdown" class="user-dropdown">
          <a target="_blank" href="https://confluence.datayes.com/pages/viewpage.action?pageId=109064547">
            <el-dropdown-item>Docs</el-dropdown-item>
          </a>
        </el-dropdown-menu>
      </el-dropdown>
      <el-tooltip style="float:right;display: flex;margin-right: 20px;" effect="dark" content="如有问题或建议，请联系yinyin.zhang" placement="left-end">
        <i class="el-icon-chat-line-round" style="font-size: small">技术支持</i>
      </el-tooltip>
    </div>

  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import Breadcrumb from '@/components/Breadcrumb'
import Hamburger from '@/components/Hamburger'
import { logout } from '@/api/user'

export default {
  components: {
    Breadcrumb,
    Hamburger
  },
  data() {
    return {
      search: '',
      appModuleAndList: [],
      category: 'appModule',
      timeout: null
    }
  },
  computed: {
    ...mapGetters([
      'sidebar',
      'avatar',
      'name'
    ])
  },
  created() {
    this.getList()
  },
  methods: {
    getList() {
      // getAllAppModuleNamesAndHosts().then(response => {
      //   for (const data of response.data) {
      //     if (data) {
      //       this.appModuleAndList.push({ 'value': data })
      //     }
      //   }
      // })
    },
    querySearchAsync(queryString, cb) {
      const restaurants = this.appModuleAndList
      const results = queryString ? restaurants.filter(this.createStateFilter(queryString.trim())) : restaurants
      clearTimeout(this.timeout)
      this.timeout = setTimeout(() => {
        cb(results)
      }, 3000 * Math.random())
    },
    createStateFilter(queryString) {
      return (search) => {
        return (search.value.toLowerCase().includes(queryString.toLowerCase()))
      }
    },
    handleSearch() {
      if (this.search.includes('.')) {
        this.category = 'host'
      }
      this.$router.push({ path: '/appModuleDetail', query: { search: this.search, category: this.category }})
    },
    toggleSideBar() {
      this.$store.dispatch('app/toggleSideBar')
    },
    async logout() {
      logout().then(response => {
        window.location.href = window.config.CAS_LOGOUT_URL + "?service=" + window.config.WEB_LOGIN_URL
      })
    }
  }
}
</script>

<style lang="scss" scoped>
.navbar {
  height: 50px;
  overflow: hidden;
  position: relative;
  background: #fff;
  box-shadow: 0 1px 4px rgba(0, 21, 41, .08);

  .hamburger-container {
    line-height: 46px;
    height: 100%;
    float: left;
    cursor: pointer;
    transition: background .3s;
    -webkit-tap-highlight-color: transparent;

    &:hover {
      background: rgba(0, 0, 0, .025)
    }
  }

  .breadcrumb-container {
    float: left;
  }

  .right-menu {
    float: right;
    height: 100%;
    line-height: 50px;

    &:focus {
      outline: none;
    }

    .right-menu-item {
      display: inline-block;
      padding: 0 8px;
      height: 100%;
      font-size: 18px;
      color: #5a5e66;
      vertical-align: text-bottom;

      &.hover-effect {
        cursor: pointer;
        transition: background .3s;

        &:hover {
          background: rgba(0, 0, 0, .025)
        }
      }
    }

    .avatar-container {
      margin-right: 30px;

      .avatar-wrapper {
        margin-top: 5px;
        position: relative;

        .user-avatar {
          cursor: pointer;
          width: 40px;
          height: 40px;
          border-radius: 10px;
        }

        .el-icon-caret-bottom {
          cursor: pointer;
          position: absolute;
          right: -20px;
          top: 25px;
          font-size: 12px;
        }
      }
    }
  }
}
</style>
