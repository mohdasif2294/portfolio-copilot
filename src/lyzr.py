# # from dataclasses import dataclass


# a = [1, 2, 3]
# b = a
# a = a + [4]
# print(b)


# def find_first_non_duplicate(word:str)-> str:
#     word_count = {}
#     for i in word:
#         if i in word_count:
#             word_count[i] += 1
#         else:
#             word_count[i] = 1
#     for i in word:
#         if word_count[i] == 1:
#             return i
#     return None

# print(find_first_non_duplicate("helloh"))
  

# def is_duplicate(num_list:[int])-> bool:
#     if len(num_list) != len(set(num_list)):
#         return True
#     return False

# print(is_duplicate([1,2,3,4,5]))
# print(is_duplicate([1,2,3,4,5,5]))

# def is_duplicate(num_list:[int])-> bool:
#     if len(num_list) != len(set(num_list)):
#         return True
#     return False

# print(is_duplicate([1,2,3,4,5]))


a = [1, 2, 3]
b = a
b = b + [4]
print(a)