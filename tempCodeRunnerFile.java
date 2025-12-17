public class Test {

    private int ;
    private int b;
    public Test(int a, int b) {
        this.a = a;
        this.b = b;
    }

    public int getA() {
        return a;
    }

    public int getB() {
        return b;
    }
    
    public void setA(int a) {
        this.a = a;
    }

    public void setB(int b) {
        this.b = b;
    }

    public int sum(){
        return a+b;
    }

    public int multiply(){
        return a*b;
    }
    

    public static void main(String[] args) {
        System.out.println("Hello, World!");
    }
}


Test = new Test(3, 4);

System.out.println("Sum: " + Test.sum());