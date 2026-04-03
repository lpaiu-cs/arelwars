cmake_minimum_required(VERSION 3.22.1)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

project("arelwars2-bootstrap")

add_library(cocos2d SHARED empty_lib.cpp)
add_library(cocosdenshion SHARED empty_lib.cpp)
add_library(openslaudio SHARED empty_lib.cpp)

add_library(gameDSO SHARED game_dso.cpp)

target_link_libraries(cocos2d android log)
target_link_libraries(cocosdenshion android log)
target_link_libraries(openslaudio android log)
target_link_libraries(gameDSO android GLESv2 log)

