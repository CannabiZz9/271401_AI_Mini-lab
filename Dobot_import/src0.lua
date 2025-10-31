function string_toArray(string,separator)
 local tab = {}
 string.gsub(string, separator, function(w) table.insert(tab, w) end )
 return tab
end
resultCreate1,socket1 = TCPCreate(true, '192.168.1.6', 6601)
  if resultCreate1 == 0 then
      print("Create TCP Server Success!")
  else
      print("Create TCP Server failed, code:", resultCreate1)
  end
  resultCreate1 = TCPStart(socket1, 0)
  if resultCreate1 == 0 then
      print("Listen TCP Client Success!")
  else
      print("Listen TCP Client failed, code:", resultCreate1)
  end
  check = "found"
check_begin = "hi"
position_Tool = 0
count = 0
Z_keep = -139
P1.coordinate[4]=0
Sync()
while not (test==check_begin) do
  resultRead1,test = TCPRead(socket1, 999, 'string')
  test = test.buf
  Sync()
  print('Wait for hi!')
end
Sync()
while 1 do
  resultWrite1 = TCPWrite(socket1, 'start')
  MovL((P1))
  resultRead1,data_check = TCPRead(socket1, 999, 'string')
  data_check = data_check.buf
  Sync()
  print(data_check)
  Sync()
  if data_check==check then
    resultWrite1 = TCPWrite(socket1, 'pos?')
    resultRead1,position = TCPRead(socket1, 999, 'string')
    position = position.buf
    Sync()
    print(position)
    position_Tool = string_toArray(position,'[^'..','..']+')
    x = position_Tool[1]
    y = position_Tool[2]
    R = position_Tool[3]
    P2.coordinate[1]=x
    P2.coordinate[2]=y
    P2.coordinate[4]=R
    P2.coordinate[3]=-90
    MovJ((P2))
    P2.coordinate[3]=-139
    MovJ((P2))
    DO(1,1)
    Sleep(1000)
    P2.coordinate[3]=-90
    MovL((P2))
    MovL((P4))
    MovL((P5))
    Sleep(3 * 1000)
    DO(1,0)
    Sleep(2 * 1000)
    DO(2,1)
    Sleep(2 * 1000)
    DO(2,0)
    Sleep(1 * 1000)
    MovL((P4))
    count = count+1
    Sync()
    if (count%4)==0 then
      count = 0
      P5.coordinate[3]=((P5.coordinate[3]
      )+30)
      P5.coordinate[1]=((P5.coordinate[1])-160)
      Sync()
      print((P5.coordinate[1]
      ))
    end
    Sync()
    print(count)
    P5.coordinate[1]=((P5.coordinate[1]
    )+40)
    Sync()
    print((P5.coordinate[2]
    ))
    Sync()
    print((P5.coordinate[3]
    ))
  end
end
