from django import template

register=template.Library()



@register.simple_tag
def installment_course_price(order_id):
    
    # print(enroll_user.course_price)
    installment_price={'2nd':order_id.course_amount/2,'3rd':order_id.course_amount/3}

    return installment_price

