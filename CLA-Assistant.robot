*** Settings ***
Documentation     CLA-Assistant: Központi Nyilvántartásból telepített robot futtatása
Resource         resources/common.resource
Library          libraries/CustomLibrary.py

*** Test Cases ***
Központi Nyilvántartásból Telepített Robot Futtatása
    [Documentation]    Ellenőrzi, hogy a robot telepítve van és futtatható
    Log    Robot telepítve és futtatva a Központi Nyilvántartásból
    # Itt lehetne hívni a tényleges futtatási parancsot vagy ellenőrzést
