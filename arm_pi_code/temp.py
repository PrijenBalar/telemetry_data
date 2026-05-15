name = ""
age = 0

class Human:
    def __init__(self):
        self.name = "Human"
        self.age = 10

    def name_change(self,name):
        self.name = name

    def details(self):
        return self.name + " " + str(self.age)

    # def age(self,age):
    #     self.age = age




if __name__ == '__main__':
    human1 = Human()

    human2 = Human()

    human1.name_change("Anil")

    human2.name_change("Prijen")

    human1.age = 26
    human2.age = 22


    # print(human1.name)
    # print(human2.name)
    # print(human1.age)
    # print(human2.age)
    print(human1.details())
    print(human2.details())


