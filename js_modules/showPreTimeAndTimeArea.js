define(function(require, exports, module) {
	srvMap.add("qryTimeArea", "common/qryTimeArea.json", "QRY_TIME_AREA");
	var util = require('util');

	var Common = require("js/common/common");
    var chooseScheduledTime = require('rboss/broadband/js/chooseScheduledTime.js');// 预约时间点选择模块
	var utilLoadCommon = Common.AILoad();
	utilLoadCommon.setContent('查询中...');


	var showPreTimeAndTimeArea = {
		timeAreaCache : {
			timeAreaMap:new Map(),
			coverageArea:'',//覆盖区域
			selectFlag:false,
			showTimeAreaFlag:false,//是否展示预约时间段，默认不展示
			preTimeNode:'#appointmentTime',//默认预约时间dome节点
			preTimeSpaceNode:'#yuTime',//默认预约时间点击事件dome节点
			deletePreTimeImgNode:'.shan_chu_img',//删除预约时间图标
			timeAreaNode:'#appointmentTimeSpace',//默认时间段dome节点
			yuTimeSpaceNode:'#yuTimeSpace',//预约时间段点击事件
			deleteYuTimeSpaceImgNode:'.shan_chu_yu_timeSpace_img',//预约时间段删除图标
//			intradayServiceNode:'#intradayService',//默认当日装dome节点
//			isFormal:1,//默认是直接受理，预受理和直接受理当日装的提示不同
//			hour:16,//当日装的场景下，16点前可以选择当日装
			intradayService:0,//是否当日装，0：非当日装，1：当日装
			canSelectArr:[],
            gotoPreTime:'',
            gotoPreTimeStep:'',
			isDefaultSelected:true //预约安装时间是否默认选中第二天，默认是
		},
		initParam:function(param){
			var self = this;
			//默认保持这个
			self.timeAreaCache.timeAreaMap = new Map();
			self.timeAreaCache.timeAreaMap.put('08:00-10:00',3);
			self.timeAreaCache.timeAreaMap.put('10:00-12:00',4);
			self.timeAreaCache.timeAreaMap.put('12:00-14:00',5);
			self.timeAreaCache.timeAreaMap.put('14:00-16:00',6);
			self.timeAreaCache.timeAreaMap.put('16:00-18:00',7);
			self.timeAreaCache.timeAreaMap.put('18:00-20:00',8);
			self.timeAreaCache.coverageArea = param.coverageArea;
			self.timeAreaCache.showTimeAreaFlag = param.showTimeAreaFlag;
			if(param.preTimeNode){
				self.timeAreaCache.preTimeNode = param.preTimeNode;
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
		},
		//设置是否当日装1：当日装；0：非当日装
		setIntradayService:function(flag){
			var self = this;
			self.timeAreaCache.intradayService = flag;

		},
		init:function(qryParam,callback){
			var self = this;
			var callbackArr = [],canSelectHours = [];
			//callbackArr中存放前三天的时间和时间段
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
				Rose.ajax.postJson(srvMap.get('qryTimeArea'),qryParam,function(json,status){
					utilLoadCommon.done();
					if(status){
						var schedules = json.schedules;
						if(schedules.length){
							for(var i =0,len = schedules.length;i<len;i++){
								var dayHours = {},schedulesHours = schedules[i].hours,
									schedulesHoursMap = new Map(),isHasCanSelectHoursFlag = false;
								//isHasCanSelectHoursFlag 有线返回的该天的可选时间段和我定义的不匹配，导致6个时间段都已满

								for(var j=0,jLen = schedulesHours.length;j < jLen;j++){
									schedulesHoursMap.put(schedulesHours[j],1);
								}
								dayHours.day = schedules[i].day;
								dayHours.hours = JSON.parse(JSON.stringify(canSelectHours));
								if(schedulesHours.length == 0){
									for(var j=0,jLen = dayHours.hours.length;j < jLen;j++){
										dayHours.hours[j].text = dayHours.hours[j].text + '(已满)';
										dayHours.hours[j].disabled = true;
									}
									dayHours.hours.push({text:'任意时间段',value:9});
								}else{
									for(var j=0,jLen = dayHours.hours.length;j < jLen;j++){
										if(!schedulesHoursMap.get(dayHours.hours[j].text)){
											//如果接口返回的时间段不包含当前遍历的时间段，就标记为已满
											dayHours.hours[j].text = dayHours.hours[j].text + '(已满)';
											dayHours.hours[j].disabled = true;
										}else{
											//有线返回的该天有可以选择的时间段
											isHasCanSelectHoursFlag = true;
										}
									}
									if(!isHasCanSelectHoursFlag){
										dayHours.hours.push({text:'任意时间段',value:9});
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
		returnAllTimeArea:function(canSelectHours,callback){
				var today = new Date();
				var hour = today.getHours();
				var canHour;
				var count = 0;
            	var tempHours = JSON.parse(JSON.stringify(canSelectHours));
            	//对当日的时间进行判断，现在时间点的后面时间段可选，其他的时间段加上已满字样，不可选
                for (var i = 0; i < 6; i++){
             	   canHour = tempHours[i].text.split(":")[0];
             	   if (canHour / hour <= 1){
               		 	tempHours[i].text += "(已满)";
                    count ++;
              	  }
                }
                //如果6个时间段都有已满字样，那么再加上一个任意时间段的选项
                if(count == 6){
                    tempHours.push({text:'任意时间段',value:9});
            }
			//查询失败或者不需要查询，默认所有时间段都可以选择，自动把前三天的数据返回
			var callbackArr = [{
                day:util.GetDateStr(0),
                 hours:tempHours
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
//			将日期转换成兼容IE的格式--巨坑
			var dayIE = day.replace(/-/g, "/");
//			1.获取当前天的前三天的时间
			var self = this,threeDay = util.GetDateStr(3).replace(/-/g, "/"),hours = [],hasDayFlag = false;
			if(new Date(dayIE) > new Date(threeDay)){
				//如果选中的是三天后的日期，那就都可以选
				self.timeAreaCache.timeAreaMap.eachMap(function(key,value){
					hours.push({text:key,value:value});
				});
			}else{
				//如果选中的是三天内（明天，后天，大后天）的日期，那就根据有线返回的时间段选
				for(var i=0,len = timeArr.length;i<len;i++){
					if(timeArr[i].day == day){
						hasDayFlag = true;
						hours = timeArr[i].hours;
                            break;
                        }
				}
				if(!hasDayFlag){
//					有线没有返回这一天，那就认为该天的时间段都不可选
					self.timeAreaCache.timeAreaMap.eachMap(function(key,value){
						hours.push({text:key + '(已满)',value:value,disabled:true});
					});
					//为该天拼接任意时间段
					hours.push({text:'任意时间段',value:9});
				}
				}
            $(self.timeAreaCache.timeAreaNode).val("").attr("numberVal","");
            $(self.timeAreaCache.deleteYuTimeSpaceImgNode).css('display', 'none');
			$(self.timeAreaCache.yuTimeSpaceNode).off("click").on("click",function(){
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
						});
			});
		},
		//根据宽带账号获取该宽带的addressId ,再根据addressId获取零售库存信息（）
//		qryParam{broadBillId:'',regionId:''}
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
//						无法获取到标准地址信息
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