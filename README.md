Sublime Text - XML to Grid Plugin
============

## Features:

- Display the current XML file as a grid or as a CSV file in a new view.


## Settings:

- `include_attributes` - Whether or not to show attributes in the grid.
- `field_separator` - The field separator to use.  Use a space to line up the fields.  Anything else will create a CSV-like file.

## How it works:

It finds the first element in document order that contains multiple children, and treats these children as rows for when it creates the grid.

## Example

```xml
<?xml version="1.0" ?>
<root>
  <User id="1">
    <FirstName>Fred</FirstName>
    <LastName>Bloggs</LastName>
    <UserName>bloggsf</UserName>
    <Address>
      <BuildingNumber>12</BuildingNumber>
      <Street>The Street</Street>
      <Town>Exampletown</Town>
    </Address>
  </User>
  <User id="3">
    <UserName>bloggsj</UserName>
    <FirstName>Joe</FirstName>
    <LastName>Bloggs</LastName>
    <Address>
      <BuildingNumber>9</BuildingNumber>
      <Street>Somewhere Else</Street>
      <Town>Exampletown</Town>
      <PostCode>TY12 6UA</PostCode>
    </Address>
  </User>
</root>
```

Is displayed as:

User\[@id] | User/FirstName | User/LastName | User/UserName | User/Address/BuildingNumber | User/Address/Street | User/Address/Town | User/Address/PostCode
--- | --- | --- | --- | --- | --- | --- | ---
1 | Fred | Bloggs | bloggsf | 12 | The Street | Exampletown |  
3 | Joe | Bloggs | bloggsj | 9 | Somewhere Else | Exampletown | TY12 6UA 
