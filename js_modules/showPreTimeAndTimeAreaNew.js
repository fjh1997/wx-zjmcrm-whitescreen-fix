define(function(require, exports, module) {
    //获取静态配置
    srvMap.add('getParaDetail', '','GET_PARA_DETAIL');
    //查询有线接口获取预约时间段信息
    srvMap.add("qryTimeAreaNew", "", "QRY_TIME_AREA_NEW");
    var util = require('util');

    var Common = require("js/common/common");
    var chooseScheduledTime = require('rboss/broadband/js/chooseScheduledTime.js');// 预约时间点选择模块
    var utilLoadCommon = Common.AILoad();
    utilLoadCommon.setContent('查询中...');


    var showPreTimeAndTimeArea = {
        timeAreaCache : {
            timeAreaMap:new Map(), //当调用有线失败时，前台默认的时间段数据
            timeAreaMapYX: new Map(), //当调用有线成功时，有线返回的4天后的预约时间段
            showTimeAreaFlag:false,//是否展示预约时间段，默认不展示
            preTimeNode:'#appointmentTime',//默认预约时间dome节点
            preTimeSpaceNode:'#yuTime',//默认预约时间点击事件dome节点
            deletePreTimeImgNode:'.shan_chu_img',//删除预约时间图标
            timeAreaNode:'#appointmentTimeSpace',//默认时间段dome节点
            yuTimeSpaceNode:'#yuTimeSpace',//预约时间段点击事件
            deleteYuTimeSpaceImgNode:'.shan_chu_yu_timeSpace_img',//预约时间段删除图标
            intradayService:0,//是否当日装，0：非当日装，1：当日装
            canSelectArr:[], //四天内的预约时间段的信息
            gotoPreTime:'', //选择预约时间段页面的id，例如：#JS_STEP_1_5
            gotoPreTimeStep:'', //预约时间段页面对应的步骤id，例如：1_5
            isDefaultSelected:true, //预约安装时间是否默认选中第二天，默认是
            paraDetails:[], //预约时间段静态配置表数据
            imepOpName: '', //装维人员姓名
            imepOpContract: '', //装维人员号码
            addressQry: false //是否提供给手厅的地址查询入口进入，默认否
        },
        //第一步：初始化参数
        initParam:function(param){
            var self = this;
            self.timeAreaCache.timeAreaMap = new Map();
            self.timeAreaCache.timeAreaMapYX = new Map();
            self.timeAreaCache.imepOpName = '';
            self.timeAreaCache.imepOpContract = '';
            self.timeAreaCache.paraDetails = [];
            self.qryTimeAreaConfig();
            self.timeAreaCache.showTimeAreaFlag = param.showTimeAreaFlag;
            if(param.preTimeNode){
                self.timeAreaCache.preTimeNode = param.preTimeNode;
            }
            if(param.needShowBack){
                self.timeAreaCache.needShowBack = param.needShowBack;
            }
            if(param.preTimeSpaceNode){
                self.timeAreaCache.preTimeSpaceNode = param.preTimeSpaceNode;
            }
            if(param.deletePreTimeImgNode){
                self.timeAreaCache.deletePreTimeImgNode = param.deletePreTimeImgNode;
            }
            if(param.timeAreaNode){
                self.timeAreaCache.timeAreaNode = param.timeAreaNode;
            }
            if(param.yuTimeSpaceNode){
                self.timeAreaCache.yuTimeSpaceNode = param.yuTimeSpaceNode;
            }
            if(param.deleteYuTimeSpaceImgNode){
                self.timeAreaCache.deleteYuTimeSpaceImgNode = param.deleteYuTimeSpaceImgNode;
            }
            if(param.gotoPreTimeStep){
                self.timeAreaCache.gotoPreTimeStep = param.gotoPreTimeStep;
            }
            if(param.gotoPreTime){
                self.timeAreaCache.gotoPreTime = param.gotoPreTime;
            }
            if(param.backStep){
                self.timeAreaCache.backStep = param.backStep;
            }
            if(param.backStepId){
                self.timeAreaCache.backStepId = param.backStepId;
            }
            if(param.isDefaultSelected=="false"){
                self.timeAreaCache.isDefaultSelected =false;
            }
            if(param.addressQry){
                self.timeAreaCache.addressQry = true;
            }
        },
        //查询预约时间段静态配置表
        qryTimeAreaConfig: function(){
            var self = this;
            var param = {
                paraType: 'TIME_AREA_INFO',
                paraCode: 'TIME_AREA_INFO',
            };
            Rose.ajax.postJsonSync(srvMap.get('getParaDetail'), param, function(json, status) {
                if (status) {
                    var paraDetails = json.paraDetails||[];
                    self.timeAreaCache.paraDetails = paraDetails;
                    for(var i = 0;i<paraDetails.length;i++) {
                        if(paraDetails[i].para3 == '4' || util.isNull(paraDetails[i].para3)) {
                            self.timeAreaCache.timeAreaMap.put(paraDetails[i].para1,paraDetails[i].para2);
                        }
                    }
                }
            });
        },
        //设置是否当日装1：当日装；0：非当日装
        setIntradayService:function(flag){
            var self = this;
            self.timeAreaCache.intradayService = flag;

        },
        //第二步：初始化查询有线接口
        init:function(qryParam,callback){
            var self = this;
            self.timeAreaCache.timeAreaMapYX = new Map();
            var callbackArr = [],canSelectHours = [];
            //callbackArr中存放前三天的时间和时间段
            //canSelectHours中存放前台默认的时间段
            self.timeAreaCache.timeAreaMap.eachMap(function(key,value){
                canSelectHours.push({text:key,value:value});
            });
            qryParam.serialNo = new Date().getTime() +'';
            if(typeof(qryParam.ordertype) == 'undefined'){
                qryParam.ordertype = '0';//没有传入请求类型的时候默认请求类型为装机。请求类型  0：装机 ;1：投诉
            }
            if(qryParam.ordertype == '0' && (typeof(qryParam.strongholdId) == 'undefined' || qryParam.strongholdId == '')){
                //没有资源点编号的时候就不查询有线了，直接所有时间段都可以选
                self.returnAllTimeArea(canSelectHours,function(arr){
                    self.timeAreaCache.canSelectArr = arr;
                    callback && callback(arr);
                });
            }else{
                utilLoadCommon.start();
                Rose.ajax.postJson(srvMap.get('qryTimeAreaNew'),qryParam,function(json,status){
                    utilLoadCommon.done();
                    if(status){
                        var paraDetails = self.timeAreaCache.paraDetails||[];
                        //有线返回的装维人员信息
                        self.timeAreaCache.imepOpName = json.imepOpName || '';
                        self.timeAreaCache.imepOpContract = json.imepOpContract || '';
                        //拼装有线返回的四天内的预约时间段的数据
                        var schedules = json.schedules || [];
                        if(schedules.length){
                            for(var i =0,len = schedules.length;i<len;i++){
                                var dayHours = {},schedulesHours = schedules[i].hours;
                                dayHours.day = schedules[i].day;
                                dayHours.hours = [];
                                if(schedulesHours.length == 0){
                                    dayHours.hours = [];
                                }else{
                                    for(var j0=0,jLen = schedulesHours.length;j0 < jLen;j0++){
                                        for(var k0 = 0;k0<paraDetails.length;k0++) {
                                            if(schedulesHours[j0].indexOf(paraDetails[k0].para1)>-1) {
                                                dayHours.hours.push({text:schedulesHours[j0],value:paraDetails[k0].para2});
                                            }
                                        }
                                    }
                                }
                                callbackArr.push(dayHours);
                            }
                        }else{
                            self.returnAllTimeArea(canSelectHours,function(arr){
                                callbackArr = arr;
                            });
                        }
                        self.timeAreaCache.canSelectArr = callbackArr;
                        //拼装有线返回的四天后的预约时间段的数据
                        var timeform = json.timeform||[];
                        if(timeform.length){
                            for(var j1=0,jLen = timeform.length;j1 < jLen;j1++){
                                for(var k1 = 0;k1<paraDetails.length;k1++) {
                                    if(timeform[j1].indexOf(paraDetails[k1].para1)>-1){
                                        self.timeAreaCache.timeAreaMapYX.put(timeform[j1],paraDetails[k1].para2);
                                    }
                                }
                            }
                        }
                        callback(callbackArr);
                    }else{
                        self.returnAllTimeArea(canSelectHours,function(arr){
                            self.timeAreaCache.canSelectArr = arr;
                            callback && callback(arr);
                        });
                    }
                });
            }
        },
        //查询失败或者不需要查询，默认所有时间段都可以选择，自动把前四天（今天，明天，后天，大后天）的数据返回
        returnAllTimeArea:function(canSelectHours,callback){
            var callbackArr = [{
                day:util.GetDateStr(0),
                hours:canSelectHours
            },{
                day:util.GetDateStr(1),
                hours:canSelectHours
            },{
                day:util.GetDateStr(2),
                hours:canSelectHours
            },{
                day:util.GetDateStr(3),
                hours:canSelectHours
            }];
            callback && callback(callbackArr);
        },
        //第三步：初始化预约安装时间，预约时间段组件
        showPreTimeAndTimeArea:function(canSelectArr,callback,flag){
            var self = this;
            var now = new Date();
            var year2 = now.getFullYear();
            var month2 = now.getMonth() + 1;
            var day2 = now.getDate();
            var data2 = year2+"-"+month2+"-"+day2;
            if(!canSelectArr){
                canSelectArr = self.timeAreaCache.canSelectArr;
            }
            if(callback&&flag){
                if(flag=="0"){//生效时间
                    self.timeAreaCache.preTimeSpaceNode = "#respay_effTime";
                }else if(flag=="1"){//失效时间
                    self.timeAreaCache.preTimeSpaceNode = "#respay_expTime";
                }
            }
            $(self.timeAreaCache.preTimeSpaceNode).unbind().click(function() {
                if(self.timeAreaCache.intradayService == "1"){
                    /*
                     * 选择了当日装则不允许再选择预约时间和预约时间段
                     */
                    return;
                }
                var dtPikcer = $("#datePicker").AIDtPicker({
                    type: 'date',
                    beginYear: year2,
                    endYear: year2+1,
                    beginData: data2,
                    buttons: [{
                        text: '取消',
                        action: function(datas) {
                        }
                    }, {
                        text: '确定',
                        action: function(datas) {
                            var dates = JSON.stringify(dtPikcer.get()); //此处测试
                            jsons = JSON.parse(dates);
                            var y = 0 , m = 0, d = 0,Dates ="";
                            $.each(jsons, function(index, domEle) {
                                if(index == "year"){
                                    domEle.value<10?y = "0"+domEle.value:y = domEle.value;
                                }
                                if(index == "month"){
                                    domEle.value<10?m = "0"+domEle.value:m = domEle.value;
                                }
                                if(index == "day"){
                                    domEle.value<10?d = "0"+domEle.value:d = domEle.value;
                                }
                                Dates = y + "-" + m + "-" + d;
                            });
                            if(callback){
                                callback(Dates);
                            }else{
                                $(self.timeAreaCache.preTimeNode).val(Dates);
                                if(!self.timeAreaCache.isDefaultSelected){
                                    $(self.timeAreaCache.deletePreTimeImgNode).css('display', 'inline-block');
                                }
                                self.showTimeArea(Dates,canSelectArr);//预约时间段
                            }

                        }
                    }]
                });
                dtPikcer.set({
                    'year': year2,
                    'month': month2,
                    'day': day2
                });
                //选完预约时间后预约预约时间段处清空
                $(self.timeAreaCache.timeAreaNode).val("").attr("numberVal","");
                $(self.timeAreaCache.deleteYuTimeSpaceImgNode).css('display', 'none');
            });
            //预约安装时间和时间段：默认次日上午
            self.autoTime(canSelectArr);
        },
        //默认自动选中明天
        autoTime:function(canSelectArr){
            var self = this;
//		      //默认显示第二天
            var tomoTime = new Date().getTime()+24*60*60*1000;
            //预约安装时间和时间段：默认次日上午
            var tomoDate = new Date();
            tomoDate.setTime(tomoTime);
            var tomoYea = tomoDate.getFullYear();
            var tomoMon = tomoDate.getMonth() + 1;
            var tomoDay = tomoDate.getDate();
            var currMon = tomoMon<10?"0"+tomoMon:tomoMon;
            var currDay = tomoDay<10?"0"+tomoDay:tomoDay;
            var currDate = tomoYea+"-"+currMon+"-"+currDay;
            if(self.timeAreaCache.isDefaultSelected){
                $(self.timeAreaCache.preTimeNode).val(currDate);
                $(self.timeAreaCache.deletePreTimeImgNode).css('display', 'inline-block');
            }
            $(self.timeAreaCache.deletePreTimeImgNode).unbind().click(function(e) {
                $(self.timeAreaCache.preTimeNode).val("");
                $(self.timeAreaCache.deletePreTimeImgNode).css('display', 'none');
                //预约安装时间段也给清空
                $(self.timeAreaCache.timeAreaNode).val("").attr("numberVal","");
                $(self.timeAreaCache.deleteYuTimeSpaceImgNode).css('display', 'none');
                e.stopPropagation();
            });
            //展示预约时间段
            if(self.timeAreaCache.showTimeAreaFlag){
                self.showTimeArea(currDate,canSelectArr);
            }
        },
        showTimeArea:function(day,timeArr){
            //获取有线返回的该天对应的时间段
            var dayIE = day.replace(/-/g, "/");
			//1.获取当前天的前三天的时间
            var self = this,threeDay = util.GetDateStr(3).replace(/-/g, "/"),hours = [];
            if(new Date(dayIE) > new Date(threeDay)){
                //判断有线有没有返回四天后的预约时间段数据
                if(self.timeAreaCache.timeAreaMapYX.size()>0){
                    self.timeAreaCache.timeAreaMapYX.eachMap(function(key,value){
                        hours.push({text:key,value:value});
                    });
                } else {
                    //没有则使用self.timeAreaCache.timeAreaMap：4个小时为维度
                    self.timeAreaCache.timeAreaMap.eachMap(function (key, value) {
                        hours.push({text: key, value: value});
                    });
                }
            }else if(day == util.GetDateStr(0)){
                //当天过滤不可选时间段
                for(var i2=0,len = timeArr.length;i2<len;i2++){
                    if(timeArr[i2].day == day){
                        var nowDate = new Date(),nowHour;
                        nowHour = nowDate.getHours();
                        hours =  JSON.parse(JSON.stringify(timeArr[i2].hours));
                        for(var j2 = 0;j2<hours.length;j2++) {
                            var canHour = hours[j2].text.split(":")[0];
                            if (canHour / nowHour <= 1) {
                                hours.splice(j2,1);
                                j2--;
                            }
                        }
                        break;
                    }
                }
            }else{
                //如果选中的是三天内（明天，后天，大后天）的日期，那就根据有线返回的时间段选
                for(var i=0,len = timeArr.length;i<len;i++){
                    if(timeArr[i].day == day){
                        hours = timeArr[i].hours;
                        break;
                    }
                }

            }
            //预约时间段排序，按从小到大的顺序展示
            hours = self._sort(hours);
            $(self.timeAreaCache.timeAreaNode).val("").attr("numberVal","");
            $(self.timeAreaCache.deleteYuTimeSpaceImgNode).css('display', 'none');
            $(self.timeAreaCache.yuTimeSpaceNode).off("click").on("click",function(){
                if(self.timeAreaCache.addressQry){
                    var statusPickCfg = {
                        fields : [ {
                            id : 'appointmentTimeSpace',
                            content : hours
                        } ],
                        buttons : [{
                            text : '取消'
                        },{
                            text : '确定',
                            action : function(datas) {
                                $(self.timeAreaCache.timeAreaNode).val(datas.appointmentTimeSpace.text).attr("numberVal", datas.appointmentTimeSpace.value);
                                $(".ui-picker").remove();
                                if(datas.appointmentTimeSpace.text.indexOf('20:00-22:00')>-1){
                                    util.tipError("提示","20：00-22：00时间段为夜间上门服务时间，装维上门时会额外收取夜间上门费用！");
                                }
                            }
                        } ],
                        options : {
                            rowNum : 3
                        }
                    };
                    var statusPick = $(self.timeAreaCache.timeAreaNode).AIPicker(statusPickCfg);
                    statusPick.set({'appointmentTimeSpace':""});
                } else {
                if(window.broadTvStep) {
                    window.broadTvStep.nowStep = self.timeAreaCache.gotoPreTimeStep;
                    window.broadTvStep.beforeStep = "1";
                }
                if(self.timeAreaCache.intradayService == "1"){
                    /*
                     * 选择了当日装则不允许再选择预约时间和预约时间段
                     */
                    return;
                }
                //跳转到选择时间段的新界面
                var param={
                    gotoPreTime: self.timeAreaCache.gotoPreTime,
                    gotoPreTimeStep: self.timeAreaCache.gotoPreTimeStep,
                    current: self.timeAreaCache.backStepId || "#JS_STEP_1",
                    currentStep: self.timeAreaCache.backStep || "1"
                };
                chooseScheduledTime.init(hours,param,function(result){
                    $(self.timeAreaCache.timeAreaNode).val(result.text).attr("numberVal",result.value);
                    if(self.timeAreaCache.needShowBack == "1"){
                        $(self.timeAreaCache.backStepId).show();
                    }
                });
                }
            });
        },
        //对时间段进行排序
        _sort: function(canSelectHours){
            canSelectHours.sort(function(a,b){
                var intA = parseInt(a.text.split('-')[0].split(':')[0]);
                var intB = parseInt(b.text.split('-')[0].split(':')[0]);
                return intA - intB
            });
            return canSelectHours;
        },
        //获取装维人员信息
        getImepInstallInfo: function(){
            var self = this;
            var obj = {
                imepInstallName: self.timeAreaCache.imepOpName || '',
                imepInstallphone: self.timeAreaCache.imepOpContract || ''
            };
            return obj;
        },
        //根据宽带账号获取该宽带的addressId ,再根据addressId获取零售库存信息（）
		//qryParam{broadBillId:'',regionId:''}
        getBroadAddressInfo:function(qryParam,callback){
            var self = this;
            //根据宽带号码查询用户信息查询
            srvMap.add('qryBroadUserInfo', 'rboss/broadtv/userInfo.json','BROAD_TV_QRY_USER_PC');
            utilLoadCommon.start();
            Rose.ajax.postJson(srvMap.get('qryBroadUserInfo'),qryParam,function(json,status){
                utilLoadCommon.done();
                if(status){
                    var addressId = json.userInfo.addressId;
                    if(addressId !=""){
                        self.getAddressInfoByAddrId({
                            regionId:qryParam.regionId,
                            addressId:addressId
                        },callback);
                    }else{
						//无法获取到标准地址信息
                        callback({},false);
                    }
                }else{
                    callback(json,status);
                }
            });
        },
        //根据地市和地址编号获取地址的详细信息
        getAddressInfoByAddrId:function(qryParam,callback){
            var self = this;
            if(typeof(qryParam.addressId) == 'undefined' || qryParam.addressId == null ||qryParam.addressId == ''){
                //没有标准地址的时候直接返回空对象
                callback && callback({},false);
                return;
            }
            //查询接入方式
            srvMap.add('qryAccessWay', 'rboss/broadband/isAccessWay.json', 'QRY_RBOSS_BROADBAND_ACCESSWAY');
            var qryAccessWay = {
                region_code:qryParam.regionId,
                addr_id:qryParam.addressId
            }

            utilLoadCommon.start();
            Rose.ajax.postJson(srvMap.get('qryAccessWay'),qryAccessWay,function(json,status){
                utilLoadCommon.done();
                callback && callback(json,status);
            });
        }
    };
    module.exports = showPreTimeAndTimeArea;


})