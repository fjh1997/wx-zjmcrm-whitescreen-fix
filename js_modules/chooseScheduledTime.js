//2019年11月1次 新增的预约时间段界面
define(function(require, exports, module) {
    var util = require('util');
    module.exports=chooseScheduledTime(util);
});
function chooseScheduledTime(util){
    var chooseScheduledTime = {
        init: function (hours,param,callback) {
            this.addCss();
            //选择的时间段
            var choosedTime={};
            $(param.current).hide();
            $(param.gotoPreTime).show();
            Rose.ajax.getHtml("tpl/selectTime.tpl",function(html,status) {
                //所有时间段展示
                var templeta = Handlebars.compile(html);
                var tempFun =  templeta(hours);
                $(param.gotoPreTime).html(tempFun);
                gotoStep(param.gotoPreTimeStep);
                $("#selectTime ul li").addClass("canchoose")
                for(var i=0;i<hours.length;i++)
                {
                    if(hours[i].text.indexOf("已满") != -1){
                        //如果有已满字样的，表示这个时间段不可选，置灰
                        $("#selectTime ul li:eq("+i+")").addClass("unclick").removeClass("canchoose");
                    }
                }
                //选中某一个时间段的时间
                $(".everyTime").on("click",function () {
                    if($(this).hasClass("canchoose")) {
                        $(this).siblings().removeClass('checked');
                        $(this).addClass("checked");
                        $("#confirm_btn").addClass("btn-blue");
                        choosedTime = {
                            text: $(".checked .chooseTime").text(),
                            value: $(".everyTime.checked").attr('value')
                        };
                        if($(this).find('label')[0].innerText.indexOf('20:00-22:00')>-1){
                            util.tipError("提示","20：00-22：00时间段为夜间上门服务时间，装维上门时会额外收取夜间上门费用！");
                        }
                    }
                });
                //受理提交事件
                $("#goback_btn").on("click",function(){
                    if($("#confirm_btn").hasClass("btn-blue")){
                    $(param.gotoPreTime).hide();
                    gotoStep(param.currentStep);
                    callback(choosedTime);}
                });
            });
        },
        addCss: function(){
            var css;
            if(!css){
                css = $("<link>").attr({
                    rel:"stylesheet",
                    type:"text/css",
                    href:seajs.data.base+"rboss/broadband/css/selectTime.css"
                }).appendTo($("head"));
            }
        }
    }
        return  chooseScheduledTime;
    }